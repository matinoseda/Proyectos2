import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import time
import numpy as np

# --- Load secrets ---
PROJECT_URL = st.secrets["PROJECT_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]               # anon key
SERVICE_ROLE_KEY = st.secrets.get("SUPABASE_SERVICE_ROLE")  # optional

def replace_table_with_retry(admin_client: Client, user_id: str, records: list, max_attempts: int = 2, sleep_time: float = 0.5):
    """
    Reemplaza los datos de 'user_data2' por los nuevos 'records' de forma segura usando una tabla temporal,
    con retry en caso de fallo en las inserciones o borrados.
    """
    if not admin_client or not records:
        st.warning("No se pueden procesar los registros: admin_client no disponible o lista vacía.")
        return False

    # --- Insertar en tabla temporal ---
    attempt = 0
    inserted_tmp = False
    tmp_records = [{**r, "user_id": user_id} for r in records]  # Asegurarse de que user_id esté presente
    while attempt < max_attempts and not inserted_tmp:
        try:
            resp_tmp = admin_client.table("user_data2_tmp").insert(tmp_records).execute()
            if getattr(resp_tmp, "error", None):
                raise Exception(resp_tmp.error)
            inserted_tmp = True
        except Exception as e_tmp:
            attempt += 1
            if attempt < max_attempts:
                time.sleep(sleep_time)
            else:
                st.error(f"Error al insertar en tabla temporal después de {max_attempts} intentos: {e_tmp}")
                return False

    # --- Borrar tabla original y reemplazar con temporal ---
    attempt_replace = 0
    replaced = False
    while attempt_replace < max_attempts and not replaced:
        try:
            # Borrar datos originales
            admin_client.table("user_data2").delete().eq("user_id", user_id).execute()

            # Leer datos de la tabla temporal
            tmp_resp = admin_client.table("user_data2_tmp").select("*").eq("user_id", user_id).execute()
            tmp_records_filled = tmp_resp.data or []

            # Insertar en tabla original
            if tmp_records_filled:
                insert_resp = admin_client.table("user_data2").insert(tmp_records_filled).execute()
                if getattr(insert_resp, "error", None):
                    raise Exception(insert_resp.error)

            # Borrar tabla temporal
            admin_client.table("user_data2_tmp").delete().eq("user_id", user_id).execute()

            replaced = True
            st.toast("✅ Cambios guardados correctamente", icon="💾")
            time.sleep(0.8)
            return True

        except Exception as e:
            attempt_replace += 1
            if attempt_replace < max_attempts:
                time.sleep(sleep_time)
            else:
                st.error(f"Error reemplazando la tabla original después de {max_attempts} intentos: {e}")
                return False


# --- Create clients ---
supabase: Client = create_client(PROJECT_URL, SUPABASE_KEY)
admin_client = create_client(PROJECT_URL, SERVICE_ROLE_KEY) if SERVICE_ROLE_KEY else None

# --- Streamlit UI ---
st.set_page_config(page_title="Precios Argentinos",layout="centered") # page_icon="🔐"
st.title("🔐 Simple Gmail Login with Supabase")

tab1, tab2, tab3 = st.tabs(["Login", "Sign Up", "Delete Account"])

# --- LOGIN ---
with tab1:
    st.subheader("Iniciar Sesión")
    email = st.text_input("📧 Dirección de Email", key="login_email")
    password = st.text_input("🔑 Contraseña", type="password", key="login_password")
    login_btn = st.button("Iniciar Sesión")

    if login_btn:
        if not email or not password:
            st.warning("Por favor ingresá email y contraseña.")
        else:
            try:
                result = supabase.auth.sign_in_with_password({"email": email, "password": password})
                user = result.user
                if user:
                    st.success(f"Bienvenido, {user.email} 👋")
                    st.session_state["logged_in"] = True
                    st.session_state["email"] = user.email
                    st.session_state["user_id"] = user.id
                else:
                    st.error("Credenciales inválidas. Intenta de nuevo.")
            except Exception as e:
                st.error(f"Login failed: {e}")

# --- SIGN UP ---
with tab2:
    st.subheader("Crear Cuenta")
    email_signup = st.text_input("📧 Email", key="signup_email")
    password_signup = st.text_input("🔑 COntraseña", type="password", key="signup_password")
    signup_btn = st.button("Crear Cuenta")

    if signup_btn:
        if not email_signup or not password_signup:
            st.warning("Por favor completá todos los campos.")
        # elif not email_signup.endswith("@gmail.com"):
        #     st.warning("Only Gmail addresses are allowed.")
        else:
            try:
                result = supabase.auth.sign_up({"email": email_signup, "password": password_signup})
                user = result.user
                if user:
                    st.success(f"¡Cuenta creada! Se envió un correo de verificación a {user.email}.")
                else:
                    st.error("Error al crear la cuenta. Intentá de nuevo.")
            except Exception as e:
                st.error(f"Error during sign-up: {e}")

# --- DELETE ACCOUNT ---
with tab3:
    st.subheader("⚠️ Eliminar Cuenta")
    email_del = st.text_input("📧 Confirmar dirección de Email", key="del_email")
    password_del = st.text_input("🔑 Confirmar contraseña", type="password", key="del_password")
    delete_btn = st.button("Eliminar mi cuenta permanentemente")

    if delete_btn:
        if not email_del or not password_del:
            st.warning("Por favor ingresá email y contraseña.")
        else:
            try:
                # Verify login first
                result = supabase.auth.sign_in_with_password({"email": email_del, "password": password_del})
                user = result.user
                if not user:
                    st.error("Credenciales inválidas.")
                else:
                    if admin_client:
                        # Delete user via service_role
                        admin_client.auth.admin.delete_user(user.id)
                        st.success("✅ Cuenta eliminada con éxito.")
                    else:
                        st.error("❌ Privilegios de administrador no disponibles para eliminar la cuenta")
            except Exception as e:
                st.error(f"Error al eliminar la cuenta: {e}")

# --- SESIÓN ACTIVA ---
if st.session_state.get("logged_in"):
    user_id = st.session_state["user_id"]

    st.divider()
    st.header(" Visor de Precios")
    st.text("(Las filas sin código EAN no se guardarán)")

    if st.button("🔄 Restablecer"):
        st.session_state["refresh"] = True

    # --- Cargar datos si es la primera vez o si pidió refresh ---
    if "df" not in st.session_state or st.session_state.get("refresh", False):
        try:
            response = admin_client.table("user_data2").select("ean, price, last_modification").eq("user_id", user_id).execute()
            data = response.data or []
            aux_df = pd.DataFrame(data)
            if "last_modification" in aux_df.columns:
                aux_df["last_modification"] = pd.to_datetime(aux_df["last_modification"], errors="coerce")
            if aux_df.empty:
                aux_df = pd.DataFrame(columns=["ean", "price", "last_modification"])
                st.toast(f"CUIDADO - Trayendo datos vacíos ")
                
                
            st.session_state["df"] = aux_df.copy()
            
            if st.session_state.get("refresh", False):
                st.toast(f"Tabla refrescada - { datetime.now().strftime( "%H:%M:%S.%f" ) }")
            
        except Exception as e:
            st.session_state["df"] = pd.DataFrame(columns=["ean", "price", "last_modification"]).copy()
    
        st.session_state["refresh"] = False

    # --- Botón de refresh ---
    # if st.button("🔄 Restablecer"):
    #     st.session_state["refresh"] = True
    #     st.rerun()  # vuelve a ejecutar todo el código desde el inicio y recarga la tabla

    # --- Editor de datos ---
    edited_df = st.data_editor(
        st.session_state["df"],
        num_rows="dynamic",
        width='stretch',
        key="user_data2_editor",
        column_config={
            "ean": st.column_config.TextColumn("EAN", help="Código EAN del producto"),
            "price": st.column_config.NumberColumn("Precio", help="Precio actual en pesos"),
            "last_modification": st.column_config.DatetimeColumn("Última Fecha", help="Fecha de actualización de precio", disabled=True),
        },
    )
    
    # --- Guardar cambios ---
    if st.button("💾 Guardar cambios en Supabase"):
        try:
            edited_df["ean"].replace("", np.nan, inplace=True)
            edited_df.dropna(subset=["ean"], inplace=True)

            edited_df["last_modification"] = edited_df["last_modification"].fillna(pd.Timestamp.now()).astype(str)
            edited_df["user_id"] = user_id
 
            edited_df = edited_df.reset_index(drop=True)
            records = edited_df.to_dict(orient="records")

            # --- USANDO INSERT + DELETE SEGURO ---
            if admin_client:
                ok = replace_table_with_retry(admin_client, user_id, records)
                if ok:
                    #st.session_state["refresh"] = True  # marca para recargar
                    st.rerun()
            else:
                st.warning("No se pueden guardar los datos: admin_client no disponible.")

            # # --- BORRAR TODO USANDO admin_client ---
            # if admin_client:
            #     admin_client.table("user_data2").delete().eq("user_id", user_id).execute()
            # else:
            #     st.warning("No se pueden borrar los datos")

            # # --- INSERTAR LOS NUEVOS REGISTROS ---
            # if records:
            #     insert_resp = admin_client.table("user_data2").insert(records).execute()
            #     if getattr(insert_resp, "error", None):
            #         st.error(f"Error al insertar: {insert_resp.error}")
            #     else:
            #         st.toast("✅ Cambios guardados correctamente", icon="💾")
            #         time.sleep(0.8)
            #         # --- CARGO LA TABLA ACTUALIZADA EN LA WEB --- 
            #         try:
            #             response = supabase.table("user_data2").select("ean, price, last_modification").eq("user_id", user_id).execute()
            #             data = response.data or []
            #             df = pd.DataFrame(data)
            #         except Exception:
            #             df = pd.DataFrame(columns=["ean", "price", "last_modification"])
            # else:
            #     st.success("✅ Tabla vaciada correctamente (sin registros para insertar).")
            #     st.rerun()

        except Exception as e:
            st.error(f"Error al guardar los cambios: {e}")

# --- Logout ---
if st.button("Logout"):
    
    st.session_state.clear()
    st.rerun()

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

    # --- Cargar datos desde Supabase ---
    try:
        response = supabase.table("user_data2").select("ean, price, last_modification").eq("user_id", user_id).execute()
        data = response.data or []
        df = pd.DataFrame(data)
    except Exception:
        df = pd.DataFrame(columns=["ean", "price", "last_modification"])
    
    # --- Asegurar tipos correctos ---
    if "last_modification" in df.columns:
        df["last_modification"] = pd.to_datetime(df["last_modification"], errors="coerce").dt.date
    
    # --- Si está vacía, crear columnas ---
    if df.empty:
        df = pd.DataFrame(columns=["ean", "price", "last_modification"])
    
    # --- Editor de datos ---
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        width=True,
        key="user_data2_editor",
        column_config={
            "ean": st.column_config.TextColumn("EAN", help="Código EAN del producto"),
            "price": st.column_config.NumberColumn("Precio", help="Precio actual en pesos"),
            "last_modification": st.column_config.DateColumn("Última Fecha", help="Fecha de actualización de precio"),
        },
    )
    
    # --- Guardar cambios ---
    if st.button("💾 Guardar cambios en Supabase"):
        try:
            edited_df = edited_df.replace('', np.nan).dropna(how="all")

            edited_df["last_modification"] = edited_df["last_modification"].fillna(pd.Timestamp.now().date()).astype(str)
            edited_df["user_id"] = user_id
 
            edited_df = edited_df.reset_index(drop=True)
            records = edited_df.to_dict(orient="records")

            # --- BORRAR TODO USANDO admin_client ---
            if admin_client:
                admin_client.table("user_data2").delete().eq("user_id", user_id).execute()
            else:
                st.warning("No se pueden borrar los datos")

            # --- INSERTAR LOS NUEVOS REGISTROS ---
            if records:
                insert_resp = admin_client.table("user_data2").insert(records).execute()
                if getattr(insert_resp, "error", None):
                    st.error(f"Error al insertar: {insert_resp.error}")
                else:
                    st.toast("✅ Cambios guardados correctamente", icon="💾")
                    st.rerun()
            else:
                st.success("✅ Tabla vaciada correctamente (sin registros para insertar).")
                st.rerun()

        except Exception as e:
            st.error(f"Error al guardar los cambios: {e}")




# --- Logout ---
if st.button("Logout"):
    
    st.session_state.clear()
    st.rerun()

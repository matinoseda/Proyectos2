from financepy.utils import DayCountTypes, Date as FinDate, DayCount
import datetime as dt
from datetime import timedelta
import pandas as pd
import holidays
import logging
from dateutil.relativedelta import relativedelta

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def calc_aniosSegunConvencion(fechaInicial, fechaFinal, convencion=DayCountTypes.THIRTY_360_BOND):
    if type(fechaInicial) == str:
        fechaInicial = dt.datetime.strptime(fechaInicial, "%d-%m-%Y").date()
    if type(fechaFinal) == str:
        fechaFinal = dt.datetime.strptime(fechaFinal, "%d-%m-%Y").date()

    fechaInicial = FinDate.from_date(fechaInicial)
    fechaFinal = FinDate.from_date(fechaFinal)
    aux_dayCount = DayCount(convencion).year_frac(fechaInicial, fechaFinal)

    return aux_dayCount[0]


def calc_diasSegunConvencion(fechaInicial, fechaFinal, convencion=DayCountTypes.THIRTY_360_BOND):
    if type(fechaInicial) == str:
        fechaInicial = dt.datetime.strptime(fechaInicial, "%d-%m-%Y").date()
    if type(fechaFinal) == str:
        fechaFinal = dt.datetime.strptime(fechaFinal, "%d-%m-%Y").date()

    fechaInicial = FinDate.from_date(fechaInicial)
    fechaFinal = FinDate.from_date(fechaFinal)
    aux_dayCount = DayCount(convencion).year_frac(fechaInicial, fechaFinal)

    return aux_dayCount[1]


class BreakevenInflationCalculator:

    def __init__(self,
                 fechaVencimiento=None,
                 fechaMercado=None,

                 tf_precioVencimiento=None,
                 tf_precioMercado=None,

                 dayCountConvention=DayCountTypes.ACT_365F,

                 cer_tasaReal=None,
                 cer_precioMercado=None,
                 indiceCER_Mercado=None,
                 cer_fechaEmision=None,
                 indiceCER_inicial=None,
                 ):
        self.fechaVencimiento = fechaVencimiento
        self.fechaMercado = fechaMercado

        self.tf_precioVencimiento = tf_precioVencimiento
        self.tf_precioMercado = tf_precioMercado

        self.dayCountConvention = dayCountConvention

        self.cer_tasaReal = cer_tasaReal
        self.cer_precioMercado = cer_precioMercado
        self.indiceCER_Mercado = indiceCER_Mercado
        self.cer_fechaEmision = cer_fechaEmision
        self.indiceCER_inicial = indiceCER_inicial

        # Cálculos NO iniciales

        # self.i es el interés simple del bono_tf entre las fechas de liquidación y de vencimiento
        self.i = self.tf_precioVencimiento / self.tf_precioMercado

        # maturity es la duration de ambos bonos medido en años
        
        
        self.maturity_tf = calc_aniosSegunConvencion(fechaInicial=self.fechaMercado,
                                                     fechaFinal=self.fechaVencimiento,
                                                     convencion=self.dayCountConvention)

        self.dias_tf = calc_diasSegunConvencion(fechaInicial=self.fechaMercado,
                                             fechaFinal=self.fechaVencimiento,
                                             convencion=self.dayCountConvention)

        self.maturity_cer = calc_aniosSegunConvencion(fechaInicial=self.cer_fechaEmision,
                                                     fechaFinal=self.fechaVencimiento,
                                                     convencion=self.dayCountConvention)
        
        # r_fija es la TEA del bono_tf calculado a precio de mercado calculado el día "Fecha de Liquidación" (fechaMercado)
        self.r_fija = self.i ** (1 / self.maturity_tf) - 1

        # 100 * (CER_FINAL/self.indiceCER_inicial) * (1 + self.cer_tasaReal) = i
        #     (CER_FINAL/self.indiceCER_inicial) =  i / (100*(1 + self.cer_tasaReal))
        #     CER_FINAL =  i * self.indiceCER_inicial / (100*(1 + self.cer_tasaReal))

        # CER a la fecha de vencimiento para que el bono_tf sea breakeven al bono_cer
        self.indiceCER_final = self.i * self.indiceCER_inicial * self.cer_precioMercado / 100 /  ((1 + self.cer_tasaReal) ** self.maturity_cer)
        self.cer_precioVencimiento = 100 * self.indiceCER_final / self.indiceCER_inicial * ( (1+self.cer_tasaReal) ** self.maturity_cer)
                     
        # (1+TEA)**maturity_tf =  indiceCER_final/indiceCER_Mercado
        self.breakevenInflationTEA = (self.indiceCER_final / self.indiceCER_Mercado) ** (1 / self.maturity_tf) - 1
        self.breakevenInflationTEM = (1+self.breakevenInflationTEA) ** (1/12) - 1       

        self.interpretacionResultado = f"""
Se calculó una inflación breakeven de {round(100 * self.breakevenInflationTEA, 2)}% TEA.
Este valor de inflación implícito anualizado es el esperado por el Mercado entre las fechas {self.fechaMercado} y {self.fechaVencimiento}.                    
            """
        self.IPCs = IPC_publication_months(self.fechaMercado, self.fechaVencimiento)

        self.imprimirCalculos = f"""

        BONO TASA FIJA:
        FECHA DE MERCADO : {self.fechaMercado}
        FECHA DE VENCIMIENTO : {self.fechaVencimiento}
        PRECIO DE MERCADO {self.tf_precioMercado}
        PAGO AL VENCIMIENTO : {self.tf_precioVencimiento}
        

        BONO CER:
        FECHA DE MERCADO : {self.fechaMercado}
        FECHA DE VENCIMIENTO : {self.fechaVencimiento}
        FECHA DE EMISIÓN : {self.cer_fechaEmision}
        PRECIO DE MERCADO: {self.cer_precioMercado}
        INTERÉS REAL AL VENCIMIENTO: {self.cer_tasaReal}
        CER DE EMISIÓN : {self.indiceCER_inicial}
        CER DE MERCADO : {self.indiceCER_Mercado}

        -----------------  -----------------
        CONVENCIÓN DE DÍAS : {self.dayCountConvention}

        MATURITY DE AMBOS BONOS [AÑOS]: {round(self.maturity_tf, 2)}
        MATURITY DE AMBOS BONOS [DÍAS]: {self.dias_tf}
        MATURITY DESDE EMISIÓN, HASTA VENCIMIENTO DEL BONO CER [AÑOS] : {round(self.maturity_cer, 2)} 

        -----------------  -----------------
        
        CÁCULOS:

        Interés simple que paga el bono tasa fija en el mercado : {round((self.i-1)*100, 2)} %
        TEA bono tasa fija en el mercado: {round(self.r_fija*100, 2)} %
        CER AL VENCIMIENTO : {round(self.indiceCER_final, 4)}
        PAGO AL VENCIMIENTO BONO CER (SUPONIENDO BREAK-EVEN INFLATION) : ${round(self.cer_precioVencimiento, 2)}
        BREAK-EVEN INFLATION (TEA): {round(self.breakevenInflationTEA*100, 2)} %
        BREAK-EVEN INFLATION (TEM): {round(self.breakevenInflationTEM*100, 2)} %

        IPCS INVOLUCRADOS EN EL CÁLCULO DEL CER DEL BONO TASA FIJA : {self.IPCs}
        
        """

def restar10DiasHabiles(fecha, dias_a_restar=10, format='%Y-%m-%d'):
    fecha_inicial = fecha
    dias_a_restar_inicial = dias_a_restar
    print(f'Restando {dias_a_restar} días hábiles: a la fecha: {fecha_inicial}')
    logging.warning(f'Restando {dias_a_restar} días hábiles: a la fecha: {fecha_inicial}')
    feriados_inamovibles = {
        (1, 1),  # Año Nuevo
        (3, 24),  # Día Nacional de la Memoria por la Verdad y la Justicia
        (4, 2),  # Día del Veterano y de los Caídos en la Guerra de Malvinas
        (5, 1),  # Día del Trabajador
        (5, 25),  # Día de la Revolución de Mayo
        (6, 20),  # Paso a la Inmortalidad del General Manuel Belgrano
        (7, 9),  # Día de la Independencia
        (12, 8),  # Día de la Inmaculada Concepción de María
        (12, 25)  # Navidad
    }
    AR_holidays = holidays.AR()

    if type(fecha) == str:
        fecha = dt.datetime.strptime(fecha, "%d-%m-%Y").date()
    mes_dia = (fecha.month, fecha.day)

    while dias_a_restar:
        if fecha not in AR_holidays and mes_dia not in feriados_inamovibles and fecha.weekday() < 5:  # ES DIA HABIL
            fecha -= pd.Timedelta(days=1)
            mes_dia = (fecha.month, fecha.day)
            dias_a_restar -= 1
        else:  # SI NO ES DIA HABIL:
            print(f'feriado detectado!!: {fecha}')
            logging.warning(f'feriado detectado!!: {fecha}')
            fecha -= timedelta(days=1)
            mes_dia = (fecha.month, fecha.day)
    print(f'Se restaron  {dias_a_restar} días hábiles: a la fecha: {fecha_inicial}, resultado: {fecha}')
    logging.warning(f'Se restaron  {dias_a_restar_inicial} días hábiles: a la fecha: {fecha_inicial}, resultado: {fecha}')
    return fecha.strftime(format)

def sumarXDiasHabiles(fecha, diasASumar=1, format='%Y-%m-%d', returnDate=False):
    fecha_inicial = fecha
    diasASumarInicial = diasASumar
    print(f'Sumando {diasASumar} días habíles: a la fecha: {fecha}')
    feriados_inamovibles = {
        (1, 1),  # Año Nuevo
        (3, 24),  # Día Nacional de la Memoria por la Verdad y la Justicia
        (4, 2),  # Día del Veterano y de los Caídos en la Guerra de Malvinas
        (5, 1),  # Día del Trabajador
        (5, 25),  # Día de la Revolución de Mayo
        (6, 20),  # Paso a la Inmortalidad del General Manuel Belgrano
        (7, 9),  # Día de la Independencia
        (12, 8),  # Día de la Inmaculada Concepción de María
        (12, 25)  # Navidad
    }
    AR_holidays = holidays.AR()

    if type(fecha) == str:
        fecha = dt.datetime.strptime(fecha, "%d-%m-%Y").date()
    mes_dia = (fecha.month, fecha.day)

    while diasASumar:
        fecha += pd.Timedelta(days=1)
        mes_dia = (fecha.month, fecha.day)
        if fecha not in AR_holidays and mes_dia not in feriados_inamovibles and fecha.weekday() < 5:  # ES DIA HABIL
            diasASumar -= 1
        else:  # NO ES DIA HABIL:
            logging.warning(f'feriado detectado!!: {fecha}')

    while fecha in AR_holidays or mes_dia in feriados_inamovibles or fecha.weekday() > 4: #NO ES DíA HABIL (para que el último día caiga en un día hábil)
        fecha += pd.Timedelta(days=1)
        mes_dia = (fecha.month, fecha.day)
    if not returnDate:
        return fecha.strftime(format)
    else:
        return fecha

def generar_lista_mes_ano(mes_inicial, ano_inicial, mes_final, ano_final):
    start_date = dt.datetime(ano_inicial, mes_inicial, 1)
    end_date = dt.datetime(ano_final, mes_final, 1)

    result = []
    current_date = start_date
    while current_date <= end_date:
        result.append(current_date.strftime("%B%Y").capitalize())
        current_date += relativedelta(months=1)

    return result

def mes_anterior(mes, año, cantidad=1):
    fecha = dt.datetime(año, mes, 1) - relativedelta(months=cantidad)
    return fecha.month, fecha.year


def IPC_publication_months(start_date, end_date):
    feriados_inamovibles = {
        (1, 1),  # Año Nuevo
        (3, 24),  # Día Nacional de la Memoria por la Verdad y la Justicia
        (4, 2),  # Día del Veterano y de los Caídos en la Guerra de Malvinas
        (5, 1),  # Día del Trabajador
        (5, 25),  # Día de la Revolución de Mayo
        (6, 20),  # Paso a la Inmortalidad del General Manuel Belgrano
        (7, 9),  # Día de la Independencia
        (12, 8),  # Día de la Inmaculada Concepción de María
        (12, 25)  # Navidad
    }
    AR_holidays = holidays.AR()

    checkDay_inicial = 15
    while True:
        if dt.date(start_date.year, start_date.month, checkDay_inicial) not in AR_holidays and (start_date.month, checkDay_inicial) not in feriados_inamovibles and dt.date(start_date.year, start_date.month, checkDay_inicial).weekday() < 5:
            if start_date.day > checkDay_inicial:
                mes_i, year_i = mes_anterior(start_date.month, start_date.year, cantidad=1)
            else:
                mes_i, year_i = mes_anterior(start_date.month, start_date.year, cantidad=2)
            break
        else:
            logging.warning('Es feriado')
            checkDay_inicial -= 1

    checkDay_final = 15
    while True:
        if dt.date(end_date.year, end_date.month, checkDay_final) not in AR_holidays and (end_date.month, checkDay_final) not in feriados_inamovibles and dt.date(end_date.year, end_date.month, checkDay_final).weekday() < 5:
            if end_date.day > checkDay_final:
                mes_f, year_f = mes_anterior(end_date.month, end_date.year, cantidad=1)
            else:
                mes_f, year_f = mes_anterior(end_date.month, end_date.year, cantidad=2)
            break
        else:
            checkDay_final -= 1

    return generar_lista_mes_ano(mes_inicial=mes_i, ano_inicial=year_i, mes_final=mes_f, ano_final=year_f)



# a = BreakevenInflationCalculator(fechaVencimiento='31-10-2025',
#                              fechaMercado='27-02-2025',
#                              tf_precioVencimiento=132.82,
#                              tf_precioMercado=110.6,
#                              dayCountConvention = DayCountTypes.ACT_365F,
#                              cer_tasaReal=0,
#                              cer_precioMercado=109.7,
#                              indiceCER_Mercado=540.5638,
#                              cer_fechaEmision='31-10-2024',
#                              indiceCER_inicial=487.6705
#                              )
#
# print(a.indiceCER_final)
# print(a.breakevenInflation)
# print(a.interpretacionResultado)

# print(restar10DiasHabiles('16-9-2025'))


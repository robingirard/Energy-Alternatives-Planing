import os
from datetime import datetime
import warnings
#warnings.filterwarnings("ignore")

import pandas as pd
import pickle
if os.path.basename(os.getcwd())=="Simulations":
    os.chdir('..')
    os.chdir('..')
    os.chdir('..')## to work at project root  like in any IDE

Input_folder="Models/Belfort/"

import numpy as np
from Models.Belfort.Simulations.f_model_Belfort import *
from pyomo.core import *
from pyomo.opt import SolverFactory
from time import time

### Functions definition (to run the model).

def labour_ratio_cost(df):  # higher labour costs at night
    if df.hour in range(6, 22):
        return 1
    else:
        return 1.3

def run_model(year,bati_hyp='ref',reindus='reindus',nuc='plus'):
    '''
    Loads data and runs a singlenode model. Now deprecated because hydrogen
    for final use is not merged with hydrogen for grid use.
    See model definition in the function GetElectricSystemModel_Belfort_SingleNode
    of the module Models.Belfort.Simulations.f_model_Belfort.

    :param year:
    :param bati_hyp:
    :param reindus:
    :param nuc:
    :return: optimized variables of the model (denoted by Pvar for problem variables
    and Dvar decision variables at the end) saved in a file.
    '''
    t1=time()
    print("Loading parameters")
    if year==2030:
        tech_suffix='2030'
    elif year in [2040,2050,2060] and nuc == 'plus':
        tech_suffix=str(year)+'_nuclear_plus'
    elif year in [2040, 2050, 2060] and nuc == 'minus':
        tech_suffix = str(year) + '_nuclear_minus'
    else:
        raise ValueError("Variable year should be 2030, 2040, 2050 or 2060 and variable nuc should be 'plus' or 'minus'.")

    TechParameters=pd.read_csv(Input_folder+"Prod/Technos_"+tech_suffix+".csv",decimal=',',sep=';').set_index(["TECHNOLOGIES"])
    StorageParameters=pd.read_csv(Input_folder+"Prod/Stock_technos_"+str(year)+".csv",decimal=',',sep=';').set_index(["STOCK_TECHNO"])

    ## Availability
    if year==2030:
        tech_suffix+='_nuclear_'+nuc
    NucAvailability=pd.read_csv(Input_folder+"Prod/availability_nuclear_"+tech_suffix+".csv",decimal='.',sep=';',parse_dates=['Date']).set_index('Date')

    WindSolarAvailability=pd.read_csv(Input_folder+"Prod/availabilityWindSolar.csv",decimal=',',sep=';',parse_dates=['Date']).set_index('Date')
    availabilityFactor=NucAvailability.join(WindSolarAvailability)
    HydroRiverAvailability=pd.read_csv(Input_folder+"Prod/availability_hydro_river.csv",decimal='.',sep=';',parse_dates=['Date']).set_index('Date')
    availabilityFactor = availabilityFactor.join(HydroRiverAvailability)

    availabilityFactor=availabilityFactor.rename(columns={'New nuke':'NewNuke','Old nuke':'OldNuke','availability':'HydroRiver'})
    availabilityFactor['NewHydroRiver']=availabilityFactor['HydroRiver']

    for col in TechParameters.index:
        if col not in availabilityFactor.columns:
            availabilityFactor[col]=1

    availabilityFactor=availabilityFactor.reset_index().melt(id_vars=['Date'],var_name="TECHNOLOGIES",value_name='availabilityFactor').set_index(['Date','TECHNOLOGIES'])

    ## Consumption
    conso_suffix=str(year)+'_'+reindus+'_'+bati_hyp
    try:
        areaConsumption=pd.read_csv(Input_folder+"Conso/Loads/Conso_"+conso_suffix+".csv",decimal='.',sep=';',parse_dates=['Date']).set_index('Date')
    except:
        raise ValueError("Variable bati_hyp should be 'ref' or 'SNBC'.")

    lossesRate=areaConsumption[['Taux_pertes']]

    ## Flexibility
    to_flex_consumption=areaConsumption[['Metallurgie','Conso_VE','Conso_H2']].rename(columns={'Metallurgie':'Steel','Conso_VE':'EV','Conso_H2':'H2'})
    to_flex_consumption=to_flex_consumption.reset_index().melt(id_vars=['Date'],var_name="FLEX_CONSUM",value_name='Consumption').set_index(['Date','FLEX_CONSUM'])

    areaConsumption=areaConsumption[['Consommation hors metallurgie']].rename(columns={'Consommation hors metallurgie':'areaConsumption'})

    FlexParameters=pd.read_csv(Input_folder+"Conso/Flex/Flex_"+str(year)+".csv",decimal=',',sep=';').set_index('FLEX_CONSUM')

    ## Labor ratio
    labour_ratio = pd.DataFrame()
    labour_ratio["Date"] = areaConsumption.index.get_level_values('Date')
    labour_ratio["FLEX_CONSUM"] = "Steel"
    labour_ratio["labour_ratio"] = labour_ratio["Date"].apply(labour_ratio_cost)

    for flex_consum in ["EV", "H2"]:
        u = pd.DataFrame()
        u["Date"] = areaConsumption.index.get_level_values('Date')
        u["FLEX_CONSUM"] = flex_consum
        u["labour_ratio"] = np.array(len(u["Date"]) * [1])
        labour_ratio = pd.concat([labour_ratio, u], ignore_index=True)

    labour_ratio=labour_ratio.set_index(["Date", "FLEX_CONSUM"])
    t2=time()
    print("Parameters loaded in: {} s".format(t2-t1))
    ## Model definition
    print("Defining model")
    model=GetElectricSystemModel_Belfort_SingleNode(areaConsumption, lossesRate, availabilityFactor,
                                                    TechParameters, StorageParameters,
                                                    to_flex_consumption, FlexParameters, labour_ratio)
    t3=time()
    print("Model defined in: {} s".format(t3-t2))

    ## Solving model
    print("Solving model")
    solver='mosek'
    opt = SolverFactory(solver)
    results = opt.solve(model)
    Variables = getVariables_panda_indexed(model)
    t4=time()
    print("Model solved in: {} s".format(t4 - t3))

    ## Saving model
    print("Saving results")
    with open('Models/Belfort/Simulations/Results_'+tech_suffix+'_'+bati_hyp+'_'+reindus+'.pickle', 'wb') as f:
        pickle.dump(Variables, f, protocol=pickle.HIGHEST_PROTOCOL)
    t5=time()
    print("Results were saved in: {} s".format(t5 - t4))

    print("Total timing: {} s".format(t5 - t1))
    #print(Variables)

def run_model_H2(year,bati_hyp='ref',reindus='reindus',mix='nuclear_plus'):
    '''
    Loads data and runs a singlenode model. For quick simulation, do not use for
    multinode ! Up to date with hydrogen management.
    See model definition in the function GetElectricSystemModel_Belfort_SingleNode_H2
    of the module Models.Belfort.Simulations.f_model_Belfort.

    :param year:
    :param bati_hyp:
    :param reindus:
    :param mix:
    :return: optimized variables of the model (denoted by Pvar for problem variables
    and Dvar decision variables at the end) saved in a file.
    '''
    t1=time()
    tech_suffix=str(year)+'_'+mix

    TechParameters=pd.read_csv(Input_folder+"Prod/Technos_"+tech_suffix+".csv",decimal=',',sep=';').set_index(["TECHNOLOGIES"])
    StorageParameters=pd.read_csv(Input_folder+"Prod/Stock_technos_"+str(year)+".csv",decimal=',',sep=';').set_index(["STOCK_TECHNO"])

    ## Availability
    NucAvailability=pd.read_csv(Input_folder+"Prod/availability_nuclear_"+tech_suffix+".csv",decimal='.',sep=';',parse_dates=['Date']).set_index('Date')

    WindSolarAvailability=pd.read_csv(Input_folder+"Prod/availabilityWindSolar.csv",decimal=',',sep=';',parse_dates=['Date']).set_index('Date')
    availabilityFactor=NucAvailability.join(WindSolarAvailability)
    HydroRiverAvailability=pd.read_csv(Input_folder+"Prod/availability_hydro_river.csv",decimal='.',sep=';',parse_dates=['Date']).set_index('Date')
    availabilityFactor = availabilityFactor.join(HydroRiverAvailability)

    availabilityFactor=availabilityFactor.rename(columns={'New nuke':'NewNuke','Old nuke':'OldNuke','availability':'HydroRiver'})
    availabilityFactor['NewHydroRiver']=availabilityFactor['HydroRiver']

    for col in TechParameters.index:
        if col not in availabilityFactor.columns:
            availabilityFactor[col]=1

    availabilityFactor=availabilityFactor.reset_index().melt(id_vars=['Date'],var_name="TECHNOLOGIES",value_name='availabilityFactor').set_index(['Date','TECHNOLOGIES'])

    ## Consumption
    conso_suffix=str(year)+'_'+reindus+'_'+bati_hyp
    try:
        areaConsumption=pd.read_csv(Input_folder+"Conso/Loads/Conso_"+conso_suffix+".csv",decimal='.',sep=';',parse_dates=['Date']).set_index('Date')
    except:
        raise ValueError("Variable bati_hyp should be 'ref' or 'SNBC'.")

    lossesRate=areaConsumption[['Taux_pertes']]

    ## Flexibility and H2
    to_flex_consumption=areaConsumption[['Metallurgie','Conso_VE']].rename(columns={'Metallurgie':'Steel','Conso_VE':'EV'})
    to_flex_consumption=to_flex_consumption.reset_index().melt(id_vars=['Date'],var_name="FLEX_CONSUM",value_name='Consumption').set_index(['Date','FLEX_CONSUM'])

    H2_consumption=areaConsumption[['Conso_H2']].rename(columns={'Conso_H2':'H2'})

    areaConsumption=areaConsumption[['Consommation hors metallurgie']].rename(columns={'Consommation hors metallurgie':'areaConsumption'})

    FlexParameters=pd.read_csv(Input_folder+"Conso/Flex/Flex_"+str(year)+".csv",decimal=',',sep=';').set_index('FLEX_CONSUM')

    ## Labor ratio
    labour_ratio = pd.DataFrame()
    labour_ratio["Date"] = areaConsumption.index.get_level_values('Date')
    labour_ratio["FLEX_CONSUM"] = "Steel"
    labour_ratio["labour_ratio"] = labour_ratio["Date"].apply(labour_ratio_cost)

    for flex_consum in ["EV"]:
        u = pd.DataFrame()
        u["Date"] = areaConsumption.index.get_level_values('Date')
        u["FLEX_CONSUM"] = flex_consum
        u["labour_ratio"] = np.array(len(u["Date"]) * [1])
        labour_ratio = pd.concat([labour_ratio, u], ignore_index=True)

    labour_ratio=labour_ratio.set_index(["Date", "FLEX_CONSUM"])
    t2=time()
    print("Parameters loaded in: {} s".format(t2-t1))
    ## Model definition
    print("Defining model")
    model=GetElectricSystemModel_Belfort_SingleNode_H2(areaConsumption, lossesRate, availabilityFactor,
                                                    TechParameters, StorageParameters,
                                                    to_flex_consumption, FlexParameters, labour_ratio,
                                                    H2_consumption)
    t3=time()
    print("Model defined in: {} s".format(t3-t2))

    ## Solving model
    print("Solving model")
    solver='mosek'
    opt = SolverFactory(solver)
    results = opt.solve(model)
    Variables = getVariables_panda_indexed(model)
    t4=time()
    print("Model solved in: {} s".format(t4 - t3))

    ## Saving model
    print("Saving results")
    with open('Models/Belfort/Simulations/Results_'+tech_suffix+'_'+bati_hyp+'_'+reindus+'.pickle', 'wb') as f:
        pickle.dump(Variables, f, protocol=pickle.HIGHEST_PROTOCOL)
    t5=time()
    print("Results were saved in: {} s".format(t5 - t4))

    print("Total timing: {} s".format(t5 - t1))


def run_model_multinode(year,bati_hyp='ref',reindus='reindus',mix='nuclear_plus',ev_hyp='',no_stock_fr=False,no_new_intercos=False,
                        L_areas=['BE','CH','DE','ES','GB','IT']):
    '''
    Loads data and runs a multinode model. To use for complete simulation with 7 countries :
    France (FR), Belgium (BE), Switzerland (CH), Germany (DE), Spain (ES),
    Great-Britain (GB) and Italy (IT).
    See model definition in the function GetElectricSystemModel_Belfort_MultiNode
    of the module Models.Belfort.Simulations.f_model_Belfort.

    :param year:
    :param bati_hyp: renovation hypothesis ('ref' or 'SNBC').
    :param reindus: industry hypothesis ('no_reindus', 'reindus', 'UNIDEN').
    :param mix: electricity mix hypothesis ('nuclear_plus_plus', 'nuclear_plus',
    'nuclear_plus_minus', 'nuclear_minus', '100_enr')
    :param ev_hyp: rythm of electric vehicles electrification ('' or '_fit55')
    :param no_stock_fr: True if battery storage is forbidden (to simulate a 2030
    without batteries).
    :param no_new_intercos: True if interconnections between France and foreign countries
    are maintained at 2022 level. To test for alternative flexibility and storage needs
    in this case.
    :param L_areas:
    :return: optimized variables of the model (denoted by Pvar for problem variables
    and Dvar decision variables at the end) saved in a file.
    '''
    t1=time()
    tech_suffix = str(year) + '_' + mix

    ## Tech parameters
    TechParameters_FR = pd.read_csv(Input_folder + "Prod/Technos_" + tech_suffix + ".csv", decimal=',',
                                 sep=';')
    TechParameters_FR['AREAS']='FR'
    TechParameters_FR.set_index(['AREAS','TECHNOLOGIES'],inplace=True)
    TechParameters_E= pd.read_csv(Input_folder + "Prod/Prod_Europe/Technos_Europe_" + str(year) + ".csv", decimal=',',
                                 sep=';').set_index(['AREAS','TECHNOLOGIES'])
    TechParameters=pd.concat([TechParameters_FR,TechParameters_E])

    ## Storage parameters
    if no_stock_fr:
        StorageParameters = pd.read_csv(
            Input_folder + "Prod/Prod_Europe/Stock_technos_Europe_no_stock_fr_" + str(year) + ".csv", decimal=',',
            sep=';').set_index(["AREAS", "STOCK_TECHNO"])
    else:
        StorageParameters = pd.read_csv(Input_folder + "Prod/Prod_Europe/Stock_technos_Europe_" + str(year) + ".csv", decimal=',',
                                    sep=';').set_index(["AREAS","STOCK_TECHNO"])

    ## Availability
    NucAvailability_FR = pd.read_csv(Input_folder + "Prod/availability_nuclear_" + tech_suffix + ".csv", decimal='.',
                                  sep=';', parse_dates=['Date']).set_index('Date')

    WindSolarAvailability_FR = pd.read_csv(Input_folder + "Prod/availabilityWindSolar.csv", decimal=',', sep=';',
                                        parse_dates=['Date']).set_index('Date')
    availabilityFactor_FR = NucAvailability_FR.join(WindSolarAvailability_FR)
    HydroRiverAvailability_FR = pd.read_csv(Input_folder + "Prod/availability_hydro_river.csv", decimal='.', sep=';',
                                         parse_dates=['Date']).set_index('Date')
    availabilityFactor_FR = availabilityFactor_FR.join(HydroRiverAvailability_FR)
    availabilityFactor_FR['AREAS']='FR'

    availabilityFactor=availabilityFactor_FR
    for area in L_areas:
        try:
            NucAvailability_area = pd.read_csv(Input_folder + "Prod/Prod_Europe/availability_nuclear_" + area + "_" + str(year) + ".csv",
                                         decimal='.', sep=';', parse_dates=['Date']).set_index('Date')
        except:
            NucAvailability_area=NucAvailability_FR.copy()
            NucAvailability_area['New nuke']=0
            NucAvailability_area['Old nuke']=0

        WindSolarAvailability_area = pd.read_csv(Input_folder + "Prod/Prod_Europe/availabilityWindSolar_"+area+".csv", decimal=',',
                                               sep=';', parse_dates=['Date']).set_index('Date')
        availabilityFactor_area = NucAvailability_area.join(WindSolarAvailability_area)
        HydroRiverAvailability_area = pd.read_csv(Input_folder + "Prod/Prod_Europe/availability_hydro_river_"+area+".csv", decimal='.',
                                                sep=';',parse_dates=['Date']).set_index('Date')
        availabilityFactor_area = availabilityFactor_area.join(HydroRiverAvailability_area)
        availabilityFactor_area['AREAS'] = area
        availabilityFactor = pd.concat([availabilityFactor,availabilityFactor_area])

    availabilityFactor = availabilityFactor.rename(
        columns={'New nuke': 'NewNuke', 'Old nuke': 'OldNuke', 'availability': 'HydroRiver'})
    availabilityFactor['NewHydroRiver'] = availabilityFactor['HydroRiver']

    availabilityFactor = availabilityFactor.reset_index().melt(id_vars=['AREAS','Date'], var_name="TECHNOLOGIES",
                                                               value_name='availabilityFactor').set_index(
        ['AREAS','Date', 'TECHNOLOGIES'])

    ## Consumption
    conso_suffix = str(year) + '_' + reindus + '_' + bati_hyp + ev_hyp
    areaConsumption_FR = pd.read_csv(Input_folder + "Conso/Loads/Conso_" + conso_suffix + ".csv", decimal='.',
                                      sep=';', parse_dates=['Date'])
    areaConsumption_FR['AREAS']='FR'
    areaConsumption_FR.set_index(['AREAS','Date'],inplace=True)
    areaConsumption = pd.read_csv(Input_folder + "Conso/Conso_Europe/Conso_Europe_" + str(year) + ".csv", decimal='.',
                                      sep=';', parse_dates=['Date']).set_index(['AREAS','Date'])

    areaConsumption=pd.concat([areaConsumption_FR,areaConsumption])
    lossesRate= areaConsumption[['Taux_pertes']]

    ## Flexibility and H2 consumption
    to_flex_consumption = areaConsumption[['Metallurgie', 'Conso_VE']].rename(
        columns={'Metallurgie': 'Steel', 'Conso_VE': 'EV'})
    to_flex_consumption = to_flex_consumption.reset_index().melt(id_vars=['AREAS','Date'], var_name="FLEX_CONSUM",
                                                                 value_name='Consumption').set_index(
        ['AREAS','Date', 'FLEX_CONSUM'])

    H2_consumption = areaConsumption[['Conso_H2']].rename(columns={'Conso_H2': 'H2'})

    areaConsumption = areaConsumption[['Consommation hors metallurgie']].rename(
        columns={'Consommation hors metallurgie': 'areaConsumption'})

    ## Flex parameters

    FlexParameters = pd.read_csv(Input_folder + "Conso/Conso_Europe/Flex_Europe_" + str(year) + ".csv", decimal=',',
                                 sep=';').set_index(['AREAS','FLEX_CONSUM'])

    ## Labor ratio
    labour_ratio_FR = pd.DataFrame()
    labour_ratio_FR["Date"] = areaConsumption_FR.index.get_level_values('Date')
    labour_ratio_FR["AREAS"]="FR"
    labour_ratio_FR["FLEX_CONSUM"] = "Steel"
    labour_ratio_FR["labour_ratio"] = labour_ratio_FR["Date"].apply(labour_ratio_cost)

    for flex_consum in ["EV"]:
        u = pd.DataFrame()
        u["Date"] = areaConsumption_FR.index.get_level_values('Date')
        u["AREAS"]="FR"
        u["FLEX_CONSUM"] = flex_consum
        u["labour_ratio"] = np.array(len(u["Date"]) * [1])
        labour_ratio_FR = pd.concat([labour_ratio_FR, u], ignore_index=True)

    labour_ratio=labour_ratio_FR.copy()
    for area in L_areas:
        labour_ratio_FR['AREAS']=area
        labour_ratio = pd.concat([labour_ratio, labour_ratio_FR], ignore_index=True)

    labour_ratio = labour_ratio.set_index(["AREAS","Date", "FLEX_CONSUM"])

    ## Last but not least... exchange parameters
    if no_new_intercos:
        ExchangeParameters = pd.read_csv(Input_folder + "Prod/Prod_Europe/Interconnexions.csv", decimal=',',
                                         sep=';').set_index(['AREA_from', 'AREA_to'])[['2022']].rename(
            columns={'2022': 'Exchange'})
    else:
        ExchangeParameters= pd.read_csv(Input_folder + "Prod/Prod_Europe/Interconnexions.csv", decimal=',',
                                 sep=';').set_index(['AREA_from','AREA_to'])[[str(year)]].rename(columns={str(year):'Exchange'})

    t2 = time()
    print("Parameters loaded in: {} s".format(t2 - t1))
    ## Model definition
    print("Defining model")
    model = GetElectricSystemModel_Belfort_MultiNode(areaConsumption, lossesRate, availabilityFactor,
                                                         TechParameters, StorageParameters,
                                                         to_flex_consumption, FlexParameters, labour_ratio,
                                                         H2_consumption,ExchangeParameters)
    t3 = time()
    print("Model defined in: {} s".format(t3 - t2))

    ## Solving model
    print("Solving model")
    solver = 'mosek'
    opt = SolverFactory(solver)
    results = opt.solve(model)
    Variables = getVariables_panda_indexed(model, Belfort=True)
    t4 = time()
    print("Model solved in: {} s".format(t4 - t3))

    ## Saving model
    d_no_stock_fr={True:'_no_stock_fr',False:''}
    d_no_new_intercos={True:'_no_new_intercos',False:''}
    print("Saving results")
    with open('Models/Belfort/Simulations/Results_multinode_' + tech_suffix + '_' + bati_hyp + '_' + reindus + d_no_stock_fr[no_stock_fr]+ev_hyp+d_no_new_intercos[no_new_intercos]+'.pickle',
              'wb') as f:
        pickle.dump(Variables, f, protocol=pickle.HIGHEST_PROTOCOL)
    t5 = time()
    print("Results were saved in: {} s".format(t5 - t4))

    print("Total timing: {} s".format(t5 - t1))

### Execution.

run_model_H2(2060,bati_hyp='ref',reindus='reindus',mix='nuclear_plus_plus')
run_model_multinode(2060,bati_hyp='ref',reindus='reindus',mix='nuclear_plus_plus',ev_hyp='',no_new_intercos=True)
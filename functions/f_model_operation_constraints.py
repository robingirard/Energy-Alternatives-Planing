import pandas as pd

from functions.f_tools import *

#region general constraints

def set_Operation_Constraints_energyCapacityexchange(EQs,model):
    Set_names = get_allSetsnames(model)
    my_set_names=list(Set_names)
    if allin(["FLEX_CONSUM", "AREAS", 'STOCK_TECHNO'], my_set_names):
        energyCtr_EQ = "sum(energy|TECHNOLOGIES) + sum(exchange|AREAS) + sum(storageOut-storageIn|STOCK_TECHNO) == total_consumption"
    elif allin(["FLEX_CONSUM", 'STOCK_TECHNO'], my_set_names):
        energyCtr_EQ = "sum(energy|TECHNOLOGIES) + sum(storageOut-storageIn|STOCK_TECHNO) == total_consumption"
    elif allin(["AREAS", 'STOCK_TECHNO'], my_set_names):
        energyCtr_EQ = "sum(energy|TECHNOLOGIES) + sum(exchange|AREAS) + sum(storageOut-storageIn|STOCK_TECHNO) == areaConsumption"
    elif  "AREAS" in my_set_names:
        energyCtr_EQ = "sum(energy|TECHNOLOGIES) + sum(exchange|AREAS) == areaConsumption"
    elif  'STOCK_TECHNO' in my_set_names:
            energyCtr_EQ = "sum(energy|TECHNOLOGIES) + sum(storageOut-storageIn|STOCK_TECHNO) == areaConsumption"
    else: # single area without storage
            energyCtr_EQ = "sum(energy|TECHNOLOGIES) == areaConsumption"

    EQs["energyCtr"] = {
        "domain":  ["AREAS","Date"] if "AREAS" in Set_names else ["Date"],
        "equation": energyCtr_EQ}

    EQs["CapacityCtr"] = {
        "domain"   : ["AREAS","Date","TECHNOLOGIES"] if "AREAS" in Set_names else ["Date","TECHNOLOGIES"],
        "equation" : "capacity * availabilityFactor >= energy"
    }

    if "AREAS" in Set_names:
        def exchangeCtrPlus_rule(model,a, b, t): #INEQ forall area.axarea.b in AREASxAREAS  t in Date
            if a!=b:
                return model.exchange[a,b,t]  <= model.maxExchangeCapacity[a,b] ;
            else:
                return model.exchange[a, a, t] == 0
        model.exchangeCtrPlus = Constraint(model.AREAS,model.AREAS,model.Date, rule=exchangeCtrPlus_rule)

        # TODO on peut pas mettre ces contraintes si on definit model.exchange>=0 (j'ai enlevé ce dernier) lors de la création de la variable
        def exchangeCtrMoins_rule(model,a, b, t): #INEQ forall area.axarea.b in AREASxAREAS  t in Date
            if a!=b:
                return model.exchange[a,b,t]  >= -model.maxExchangeCapacity[b,a]#[a,b] ;
            else:
                return model.exchange[a, a, t] == 0
        model.exchangeCtrMoins = Constraint(model.AREAS,model.AREAS,model.Date, rule=exchangeCtrMoins_rule)

        # TODO il n'y a pas la même capacité max en import et en export ==> cette contrainte implique qu'on limite à la plus petite capacité
        def exchangeCtr2_rule(model,a, b, t): #INEQ forall area.axarea.b in AREASxAREAS  t in Date
            return model.exchange[a,b,t]  == -model.exchange[b,a,t] ;
        model.exchangeCtr2 = Constraint(model.AREAS,model.AREAS,model.Date, rule=exchangeCtr2_rule)



    model = math_to_pyomo_constraint(EQs, model)
    return model


def set_Operation_Constraints_stockCtr(model):
    """
    limit on the stock over a year
    [if "EnergyNbhourCap"] EnergyNbhourCap *capacity >= sum energy

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    All_parameters = get_ParametersNames(model)
    if "EnergyNbhourCap" in All_parameters:
        if "AREAS" in Set_names:
            def stock_rule(model, area, tech):  # INEQ forall t, tech
                if model.EnergyNbhourCap[(area, tech)] > 0:
                    return model.EnergyNbhourCap[area, tech] * model.capacity[area, tech] >= sum(
                        model.energy[area, t, tech] for t in model.Date)
                else:
                    return Constraint.Skip
            model.stockCtr = Constraint(model.AREAS, model.TECHNOLOGIES, rule=stock_rule)
        else:
            def stock_rule(model, tech):  # INEQ forall t, tech
                if model.EnergyNbhourCap[tech] > 0:
                    return model.EnergyNbhourCap[tech] * model.capacity[tech] >= sum(
                        model.energy[t, tech] for t in model.Date)
                else:
                    return Constraint.Skip
            model.stockCtr = Constraint(model.TECHNOLOGIES, rule=stock_rule)
    return model

def set_Operation_Constraints_Ramp(model):
    """
    [if RampConstraintPlus] energy[t+1]-energy[t]<= capacity RampConstraintPlus

    [if RampConstraintMoins] energy[t+1]-energy[t]>= - capacity RampConstraintMoins

    [if RampConstraintPlus2] (energy[t+2]+energy[t+3])/2-(energy[t+1]+energy[t])/2<= capacity RampConstraintPlus2

    [if RampConstraintMoins2] (energy[t+2]+energy[t+3])/2-(energy[t+1]+energy[t])/2<= capacity RampConstraintPlus2

    :param model:
    :return:
    """

    All_parameters = get_ParametersNames(model)
    if "RampConstraintPlus" in All_parameters:
        model = set_Operation_Constraints_rampCtrPlus(model)
    if "RampConstraintMoins" in All_parameters:
        model = set_Operation_Constraints_rampCtrMoins(model)
    if "RampConstraintPlus2" in All_parameters:
        model = set_Operation_Constraints_rampCtrPlus2(model)
    if "RampConstraintMoins2" in All_parameters:
        model = set_Operation_Constraints_rampCtrMoins2(model)

    return model;

def set_Operation_Constraints_Storage(model):
    """
    is applied only if 'STOCK_TECHNO' exists

    storageIn <= Pmax

    storageOut <= Pmax

    stockLevel[t] = stockLevel[t-1]*(1 - dissipation) -storageOut/efficiency_out

    stockLevel <= Cmax

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    if 'STOCK_TECHNO' in Set_names:
        model = set_Operation_Constraints_StoragePowerUBCtr(model) # storageIn-Pmax <= 0
        model = set_Operation_Constraints_StoragePowerLBCtr(model) # storageOut-Pmax <= 0
        model = set_Operation_Constraints_StorageLevelCtr(model) # stockLevel[t] = stockLevel[t-1]*(1 - dissipation) -storageOut/efficiency_out
        model = set_Operation_Constraints_StorageCapacityCtr(model) # stockLevel <= Cmax
    return model

def set_Operation_Constraints_flex(model):
    """
    Applies only if 'FLEX_CONSUM' in Set_names

    total_consumption = areaConsumption+sum(flex_consumption)

    max_power + increased_max_power >= flex_consumption

    [if model_type == 'week'] sum(flex_consumption|week) = sum(to_flex_consumption|week)

    [if model_type == 'year']  sum(flex_consumption) = sum(to_flex_consumption)

    flex_consumption= to_flex_consumption*(1-flex)

    flex<= flex_ratio

    flex>= - flex_ratio

    flex_consumption-to_flex_consumption = a_plus +  a_minus

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    if 'FLEX_CONSUM' in Set_names:
        model   =   set_Operation_Constraints_total_consumptionCtr(model)# total_consumption = areaConsumption+sum(flex_consumption)
        model   =   set_Operation_Constraints_max_powerCtr(model)
        model   =   set_Operation_Constraints_consum_eq_day_Ctr(model)
        model   =   set_Operation_Constraints_consum_eq_week_Ctr(model)
        model   =   set_Operation_Constraints_consum_eq_year_Ctr(model)
        model   =   set_Operation_Constraints_consum_flex_Ctr(model)
        model   =   set_Operation_Constraints_flex_variation_supinf_Ctr(model)
        model   =   set_Operation_Constraints_a_plus_minusCtr(model)
    return model

#endregion

#region flex constraints

def set_Operation_Constraints_total_consumptionCtr(model):
    """
    total_consumption = areaConsumption+sum(flex_consumption)

    :param model:
    :return:
    """
    # Total consumption constraint
    # LoadCost;flex_ratio;max_ratio
    def total_consumption_rule(model, t,area):
        return model.total_consumption[area,t] == model.areaConsumption[area,t] + sum(
            model.flex_consumption[area,t, name] for name in model.FLEX_CONSUM)
    model.total_consumptionCtr = Constraint(model.Date, model.AREAS, rule=total_consumption_rule)
    return model

def set_Operation_Constraints_max_powerCtr(model):
    """
    max_power + increased_max_power >= flex_consumption

    :param model:
    :return:
    """
    # Online flexible consumption constraints
    def max_power_rule(model, area,conso_type, t):
        return model.max_power[area,conso_type] + model.increased_max_power[area,conso_type] >= model.flex_consumption[area,t, conso_type]
    model.max_powerCtr = Constraint(model.AREAS,model.FLEX_CONSUM, model.Date, rule=max_power_rule)
    return model

def set_Operation_Constraints_consum_eq_day_Ctr(model):
    """
    sum(flex_consumption|week) = sum(to_flex_consumption|week)

    :param model:
    :return:
    """
    Date_list = pd.DataFrame({"Date" : getattr(model, "Date").data()})
    Date_list["day"] = Date_list.Date.apply(lambda x: x.dayofyear)

    # consumption equality within the same week
    def consum_eq_day(model, area,t_day, conso_type):
        if model.flex_type[area,conso_type] == 'day':
            #Date_list=getattr(model, "Date").data()
            t_range = Date_list.Date[Date_list.day == t_day]  # range((t_week-1)*7*24+1,(t_week)*7*24)
            return sum(model.flex_consumption[area,t, conso_type] for t in t_range) == sum(
                model.to_flex_consumption[area,t, conso_type] for t in t_range)
        else:
            return Constraint.Skip
    model.consum_eq_day_Ctr = Constraint(model.AREAS,model.DAY_Date, model.FLEX_CONSUM, rule=consum_eq_day)
    return model
def set_Operation_Constraints_consum_eq_week_Ctr(model):
    """
    sum(flex_consumption|week) = sum(to_flex_consumption|week)

    :param model:
    :return:
    """
    Date_list = pd.DataFrame({"Date" : getattr(model, "Date").data()})
    Date_list["week"] = Date_list.Date.apply(lambda x: x.isocalendar().week)

    # consumption equality within the same week
    def consum_eq_week(model, area,t_week, conso_type):
        if model.flex_type[area,conso_type] == 'week':
            #Date_list=getattr(model, "Date").data()
            t_range = Date_list.Date[Date_list.week == t_week]  # range((t_week-1)*7*24+1,(t_week)*7*24)
            return sum(model.flex_consumption[area,t, conso_type] for t in t_range) == sum(
                model.to_flex_consumption[area,t, conso_type] for t in t_range)
        else:
            return Constraint.Skip
    model.consum_eq_week_Ctr = Constraint(model.AREAS,model.WEEK_Date, model.FLEX_CONSUM, rule=consum_eq_week)
    return model

def set_Operation_Constraints_consum_eq_year_Ctr(model):
    """
    sum(flex_consumption) = sum(to_flex_consumption)

    :param model:
    :return:
    """
    def consum_eq_year(model, area, conso_type):
        if model.flex_type[area,conso_type] == 'year':
            return sum(model.flex_consumption[area,t, conso_type] for t in model.Date) == sum(
                model.to_flex_consumption[area,t, conso_type] for t in model.Date)
        else:
            return Constraint.Skip
    model.consum_eq_year_Ctr = Constraint(model.AREAS, model.FLEX_CONSUM, rule=consum_eq_year)
    return model

def set_Operation_Constraints_consum_flex_Ctr(model):
    """
    flex_consumption= to_flex_consumption*(1-flex)

    :param model:
    :return:
    """
    def consum_flex_rule(model, area,t, conso_type):
        return model.flex_consumption[area,t, conso_type] == model.to_flex_consumption[area,t, conso_type] * (
                    1 - model.flex[area,t, conso_type])
    model.consum_flex_Ctr = Constraint(model.AREAS,model.Date, model.FLEX_CONSUM, rule=consum_flex_rule)
    return model

def set_Operation_Constraints_flex_variation_supinf_Ctr(model):
    """
    flex<= flex_ratio

    flex>= - flex_ratio

    :param model:
    :return:
    """

    def flex_variation_sup_rule(model, area,t, conso_type):
        return model.flex[area,t, conso_type] <= model.flex_ratio[area,conso_type]
    model.flex_variation_sup_Ctr = Constraint(model.AREAS,model.Date, model.FLEX_CONSUM, rule=flex_variation_sup_rule)

    def flex_variation_inf_rule(model, area,t, conso_type):
        return model.flex[area,t, conso_type] >= -model.flex_ratio[area,conso_type]
    model.flex_variation_inf_Ctr = Constraint(model.AREAS,model.Date, model.FLEX_CONSUM, rule=flex_variation_inf_rule)
    return model
    #Labour cost for flexibility consumption constraint

def set_Operation_Constraints_a_plus_minusCtr(model):
    """
    flex_consumption-to_flex_consumption = a_plus +  a_minus

    :param model:
    :return:
    """

    def a_plus_minus_rule(model,area,conso_type,t):
        return model.flex_consumption[area,t,conso_type]-model.to_flex_consumption[area,t,conso_type]==model.a_plus[area,t,conso_type]-model.a_minus[area,t,conso_type]
    model.a_plus_minusCtr=Constraint(model.AREAS,model.FLEX_CONSUM,model.Date,rule=a_plus_minus_rule)
    return model

#endregion

#region Ramp constraints
def set_Operation_Constraints_rampCtrPlus(model):
    """
    energy[t+1]-energy[t]<= capacity RampConstraintPlus

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    if "AREAS" in Set_names:
        def rampCtrPlus_rule(model, area, t, tech):  # INEQ forall t<
            if model.RampConstraintPlus[(area, tech)] > 0:
                t_plus_1 = t + timedelta(hours=1)
                return model.energy[area, t_plus_1, tech] - model.energy[area, t, tech] <= model.capacity[
                    area, tech] * \
                       model.RampConstraintPlus[area, tech] * model.availabilityFactor[area, t, tech];
            else:
                return Constraint.Skip

        model.rampCtrPlus = Constraint(model.AREAS, model.Date_MinusOne, model.TECHNOLOGIES, rule=rampCtrPlus_rule)
    else: ## AREAS not in Set_names
        def rampCtrPlus_rule(model, t, tech):  # INEQ forall t<
            if model.RampConstraintPlus[tech] > 0:
                t_plus_1 = t + timedelta(hours=1)
                return model.energy[t_plus_1, tech] - model.energy[t, tech] <= model.capacity[tech] * \
                       model.RampConstraintPlus[tech] * model.availabilityFactor[t, tech];
            else:
                return Constraint.Skip

        model.rampCtrPlus = Constraint(model.Date_MinusOne, model.TECHNOLOGIES, rule=rampCtrPlus_rule)

    return model;

def set_Operation_Constraints_rampCtrMoins(model):
    """
    energy[t+1]-energy[t]>= - capacity RampConstraintMoins

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    if "AREAS" in Set_names:
            # multiple area
            def rampCtrMoins_rule(model, area, t, tech):  # INEQ forall t<
                if model.RampConstraintMoins[area, tech] > 0.:
                    t_plus_1 = t + timedelta(hours=1)
                    return model.energy[area, t_plus_1, tech] - model.energy[area, t, tech] >= - model.capacity[
                        area, tech] * \
                           model.RampConstraintMoins[area, tech]*model.availabilityFactor[area,t,tech];
                else:
                    return Constraint.Skip
            model.rampCtrMoins = Constraint(model.AREAS, model.Date_MinusOne, model.TECHNOLOGIES,
                                            rule=rampCtrMoins_rule)
    else:
            # single area
            def rampCtrMoins_rule(model, t, tech):  # INEQ forall t<
                if model.RampConstraintMoins[tech] > 0:
                    t_plus_1 = t + timedelta(hours=1)
                    return model.energy[t_plus_1, tech] - model.energy[t, tech] >= - model.capacity[tech] * \
                           model.RampConstraintMoins[tech]**model.availabilityFactor[t,tech];
                else:
                    return Constraint.Skip
            model.rampCtrMoins = Constraint(model.Date_MinusOne, model.TECHNOLOGIES, rule=rampCtrMoins_rule)

    return model;

def set_Operation_Constraints_rampCtrPlus2(model):
    """
        (energy[t+2]+energy[t+3])/2-(energy[t+1]+energy[t])/2<= capacity RampConstraintPlus2

        :param model:
        :return:
    """
    Set_names = get_allSetsnames(model)
    if "AREAS" in Set_names:
            # multiple area
            def rampCtrPlus2_rule(model, area, t, tech):  # INEQ forall t<
                if model.RampConstraintPlus2[(area, tech)] > 0.:
                    t_plus_1 = t + timedelta(hours=1)
                    t_plus_2 = t + timedelta(hours=2)
                    t_plus_3 = t + timedelta(hours=3)
                    var = (model.energy[area, t_plus_2, tech] + model.energy[area, t_plus_3, tech]) / 2 - (
                            model.energy[area, t_plus_1, tech] + model.energy[area, t, tech]) / 2;
                    return var <= model.capacity[area, tech] * model.RampConstraintPlus2[area, tech]*model.availabilityFactor[area,t,tech];
                else:
                    return Constraint.Skip

            model.rampCtrPlus2 = Constraint(model.AREAS, model.Date_MinusThree, model.TECHNOLOGIES,
                                            rule=rampCtrPlus2_rule)
    else:
            # single area
            def rampCtrPlus2_rule(model, t, tech):  # INEQ forall t<
                if model.RampConstraintPlus2[tech] > 0:
                    t_plus_1 = t + timedelta(hours=1)
                    t_plus_2 = t + timedelta(hours=2)
                    t_plus_3 = t + timedelta(hours=3)
                    var = (model.energy[t_plus_2, tech] + model.energy[t_plus_3, tech]) / 2 - (
                            model.energy[t_plus_1, tech] + model.energy[t, tech]) / 2;
                    return var <= model.capacity[tech] * model.RampConstraintPlus2[tech]*model.availabilityFactor[t,tech];
                else:
                    return Constraint.Skip

            model.rampCtrPlus2 = Constraint(model.Date_MinusThree, model.TECHNOLOGIES, rule=rampCtrPlus2_rule)

    return model;

def set_Operation_Constraints_rampCtrMoins2(model):
    """
    (energy[t+2]+energy[t+3])/2-(energy[t+1]+energy[t])/2>= - capacity RampConstraintMoins2

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    if "AREAS" in Set_names:
            # multiple area
            def rampCtrMoins2_rule(model, area, t, tech):  # INEQ forall t<
                if model.RampConstraintMoins2[(area, tech)] > 0:
                    t_plus_1 = t + timedelta(hours=1)
                    t_plus_2 = t + timedelta(hours=2)
                    t_plus_3 = t + timedelta(hours=3)
                    var = (model.energy[area, t_plus_2, tech] + model.energy[area, t_plus_3, tech]) / 2 - (
                            model.energy[area, t_plus_1, tech] + model.energy[area, t, tech]) / 2;
                    return var >= - model.capacity[area, tech] * model.RampConstraintMoins2[area, tech]*model.availabilityFactor[area,t,tech];
                else:
                    return Constraint.Skip
            model.rampCtrMoins2 = Constraint(model.AREAS, model.Date_MinusThree, model.TECHNOLOGIES,
                                             rule=rampCtrMoins2_rule)
    else:
            # single area
            def rampCtrMoins2_rule(model, t, tech):  # INEQ forall t<
                if model.RampConstraintMoins2[tech] > 0:
                    t_plus_1 = t + timedelta(hours=1)
                    t_plus_2 = t + timedelta(hours=2)
                    t_plus_3 = t + timedelta(hours=3)
                    var = (model.energy[t_plus_2, tech] + model.energy[t_plus_3, tech]) / 2 - (
                            model.energy[t_plus_1, tech] + model.energy[t, tech]) / 2;
                    return var >= - model.capacity[tech] * model.RampConstraintMoins2[tech]*model.availabilityFactor[t,tech];
                else:
                    return Constraint.Skip
            model.rampCtrMoins2 = Constraint(model.Date_MinusThree, model.TECHNOLOGIES, rule=rampCtrMoins2_rule)

    return model;

#endregion

#region Storage Constraints

def set_Operation_Constraints_StoragePowerUBCtr(model):
    """
    storageIn-Pmax <= 0

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    if "AREAS" in Set_names:
            # multiple area
            def StoragePowerUB_rule(model, area, t, s_tech):  # INEQ forall t
                return model.storageIn[area, t, s_tech] - model.Pmax[area, s_tech] <= 0
            model.StoragePowerUBCtr = Constraint(model.AREAS, model.Date, model.STOCK_TECHNO, rule=StoragePowerUB_rule)
    else:
            # single area
            def StoragePowerUB_rule(model, t, s_tech):  # INEQ forall t
                return model.storageIn[t, s_tech] - model.Pmax[s_tech] <= 0
            model.StoragePowerUBCtr = Constraint(model.Date, model.STOCK_TECHNO, rule=StoragePowerUB_rule)

    return model

def set_Operation_Constraints_StoragePowerLBCtr(model):
    """
    storageOut-Pmax<=0

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    if "AREAS" in Set_names:
            # multiple area
            def StoragePowerLB_rule(model, area, t, s_tech, ):  # INEQ forall t
                return model.storageOut[area, t, s_tech] - model.Pmax[area, s_tech] <= 0
            model.StoragePowerLBCtr = Constraint(model.AREAS, model.Date, model.STOCK_TECHNO, rule=StoragePowerLB_rule)
    else:
            # single area
            def StoragePowerLB_rule(model, t, s_tech, ):  # INEQ forall t
                return model.storageOut[t, s_tech] - model.Pmax[s_tech] <= 0
            model.StoragePowerLBCtr = Constraint(model.Date, model.STOCK_TECHNO, rule=StoragePowerLB_rule)

    return model

def set_Operation_Constraints_StorageLevelCtr(model):
    """
    stockLevel[t] = stockLevel[t-1]*(1 - dissipation) -storageOut/efficiency_out

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    if "AREAS" in Set_names:
            # multiple area
            def StorageLevel_rule(model, area, t, s_tech):  # EQ forall t
                if t != min(getattr(model, "Date").data()):
                    t_moins_1 = t - timedelta(hours=1)
                    # print(s_tech,area,model.efficiency_in[area, s_tech])
                    return model.stockLevel[area, t, s_tech] == model.stockLevel[area, t_moins_1, s_tech] * (
                            1 - model.dissipation[area, s_tech]) + model.storageIn[area, t, s_tech] * \
                           model.efficiency_in[area, s_tech] - model.storageOut[area, t, s_tech] / model.efficiency_out[
                               area, s_tech]
                else: #TODO initialize initial stockLevel
                    return model.stockLevel[area, t, s_tech] == model.stockLevel_ini[area,s_tech]
            model.StorageLevelCtr = Constraint(model.AREAS, model.Date, model.STOCK_TECHNO, rule=StorageLevel_rule)

            def FinalStorageLevel_rule(model, area, t, s_tech):
                if t==max(getattr(model, "Date").data()): #TODO initialize final stockLevel (which is equal to initial stockLevel)
                    return model.stockLevel[area, t, s_tech] == model.stockLevel_ini[area,s_tech]
                else:
                    return Constraint.Skip
            model.FinalStorageLevelCtr=Constraint(model.AREAS,model.Date,model.STOCK_TECHNO,rule=FinalStorageLevel_rule)

            def StorageLevel_ini_rule(model, area,s_tech):
                return model.stockLevel_ini[area,s_tech] <= model.Cmax[area,s_tech]
            model.StorageLevel_iniCtr = Constraint(model.AREAS,model.STOCK_TECHNO, rule=StorageLevel_ini_rule)

    else:
            # single area
            def StorageLevel_rule(model, t, s_tech):  # EQ forall t
                if t != min(getattr(model, "Date").data()):
                    t_moins_1 = t - timedelta(hours=1)
                    return model.stockLevel[t, s_tech] == model.stockLevel[t_moins_1, s_tech] * (
                            1 - model.dissipation[s_tech]) + model.storageIn[t, s_tech] * model.efficiency_in[s_tech] - \
                           model.storageOut[t, s_tech] / model.efficiency_out[s_tech]
                else: #TODO initialize initial stockLevel
                    return model.stockLevel[t, s_tech] == model.stockLevel_ini[s_tech]
            model.StorageLevelCtr = Constraint(model.Date, model.STOCK_TECHNO, rule=StorageLevel_rule)

            def FinalStorageLevel_rule(model, t, s_tech):
                if t == max(getattr(model,"Date").data()):  # TODO initialize final stockLevel (which is equal to initial stockLevel)
                    return model.stockLevel[t, s_tech] == model.stockLevel_ini[ s_tech]
                else:
                    return Constraint.Skip
            model.FinalStorageLevelCtr = Constraint(model.Date, model.STOCK_TECHNO,rule=FinalStorageLevel_rule)

            def StorageLevel_ini_rule(model,  s_tech):
                    return model.stockLevel_ini[ s_tech] <=model.Cmax[s_tech]
            model.StorageLevel_iniCtr = Constraint( model.STOCK_TECHNO, rule=StorageLevel_ini_rule)

    return model

def set_Operation_Constraints_StorageCapacityCtr(model):
    """
    stockLevel <= Cmax

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)
    if "AREAS" in my_set_names:
            # multiple area
            def StorageCapacity_rule(model, area, t, s_tech, ):  # INEQ forall t
                return model.stockLevel[area, t, s_tech] <= model.Cmax[area, s_tech]

            model.StorageCapacityCtr = Constraint(model.AREAS, model.Date, model.STOCK_TECHNO, rule=StorageCapacity_rule)
    else:
            # single area
            def StorageCapacity_rule(model, t, s_tech, ):  # INEQ forall t
                return model.stockLevel[t, s_tech] <= model.Cmax[s_tech]
            model.StorageCapacityCtr = Constraint(model.Date, model.STOCK_TECHNO, rule=StorageCapacity_rule)

    return model

#endregion


#region oldies


def set_Operation_Constraints_CapacityCtr(model):
    """
    energy <= capacity * availabilityFactor

    :param model:
    :return:
    """
    Set_names = get_allSetsnames(model)

    ### CapacityCtr definition
    if "AREAS" in Set_names:
            #multiple area (with or without storage)
            def CapacityCtr_rule(model, area, t, tech):  # INEQ forall t, tech
                return model.capacity[area, tech] * model.availabilityFactor[area, t, tech] >= model.energy[
                    area, t, tech]
            model.CapacityCtr = Constraint(model.AREAS, model.Date, model.TECHNOLOGIES, rule=CapacityCtr_rule)

    else:
            # single area (with or without storage)
            def Capacity_rule(model, t, tech):  # INEQ forall t, tech
                return model.capacity[tech] * model.availabilityFactor[t, tech] >= model.energy[t, tech]
            model.CapacityCtr = Constraint(model.Date, model.TECHNOLOGIES, rule=Capacity_rule)
    return model

def set_Operation_Constraints_energyCtr(model):
    """
    [Default] sum(energy) = areaConsumption

    [if STOCK_TECHNO] sum(energy) + storageOut-storageIn = areaConsumption

    [if AREAS] sum(energy) + exchange = areaConsumption

    [if AREAS & STOCK_TECHNO] sum(energy|tech) + exchange + storageOut-storageIn = areaConsumption

    :param model:
    :return:
    """

    Set_names = get_allSetsnames(model)
    my_set_names=list(Set_names)
    ### CapacityCtr definition
    if allin(["FLEX_CONSUM", "AREAS", 'STOCK_TECHNO'], my_set_names):
            # multiple area and storage and flex conso

            def energyCtr_rule(model,area, t):  # INEQ forall t
                return sum(model.energy[area,t, tech] for tech in model.TECHNOLOGIES)+ sum(
                    model.exchange[b, area, t] for b in model.AREAS) + sum(
                    model.storageOut[area,t, s_tech] - model.storageIn[area,t, s_tech] for s_tech in model.STOCK_TECHNO) >= \
                       model.total_consumption[area,t]

            model.energyCtr = Constraint(model.AREAS, model.Date, rule=energyCtr_rule)


    elif allin(["FLEX_CONSUM", 'STOCK_TECHNO'], my_set_names):
            # simple area and storage and flex conso
            def energyCtr_rule(model, t):  # INEQ forall t
                return sum(model.energy[t, tech] for tech in model.TECHNOLOGIES) + sum(
                    model.storageOut[t, s_tech] - model.storageIn[t, s_tech] for s_tech in model.STOCK_TECHNO) >= \
                       model.total_consumption[t]

            model.energyCtr = Constraint(model.Date, rule=energyCtr_rule)
    elif allin(["AREAS", 'STOCK_TECHNO'], my_set_names):
            # multiple area and storage
            def energyCtr_rule(model, area, t):  # INEQ forall t
                return sum(model.energy[area, t, tech] for tech in model.TECHNOLOGIES) + sum(
                    model.exchange[b, area, t] for b in model.AREAS) + sum(
                    model.storageOut[area, t, s_tech] - model.storageIn[area, t, s_tech] for s_tech in model.STOCK_TECHNO) == \
                       model.areaConsumption[area, t]
            model.energyCtr = Constraint(model.AREAS, model.Date, rule=energyCtr_rule)



        # case [*my_set_names] if "AREAS" in my_set_names:
        #     # multiple area without storage
        #     def energyCtr_rule(model, area, t):  # INEQ forall t
        #         return sum(model.energy[area, t, tech] for tech in model.TECHNOLOGIES) + sum(
        #             model.exchange[b, area, t] for b in model.AREAS) == model.areaConsumption[area, t]
        #     model.energyCtr = Constraint(model.AREAS, model.Date, rule=energyCtr_rule)
        #
        # case [*my_set_names] if 'STOCK_TECHNO' in my_set_names:
        #     # single area with storage
        #     def energyCtr_rule(model, t):  # INEQ forall t
        #         return sum(model.energy[t, tech] for tech in model.TECHNOLOGIES) + sum(
        #             model.storageOut[t, s_tech] - model.storageIn[t, s_tech] for s_tech in model.STOCK_TECHNO) == \
        #                model.areaConsumption[t]
        #     model.energyCtr = Constraint(model.Date, rule=energyCtr_rule)

    else:
            # single area without storage
            def energyCtr_rule(model, t):  # INEQ forall t
                return sum(model.energy[t, tech] for tech in model.TECHNOLOGIES) == model.areaConsumption[t]
            model.energyCtr = Constraint(model.Date, rule=energyCtr_rule)

    return model


#endregion
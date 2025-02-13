#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 14 07:51:58 2020

@author: robin.girard
Here we test a more compact and automatic way to build models -- should result in the same models as in f_PlanningModels
pro :  easier to read, faster to be written
cons : more difficult to modify (add constraints/variables, ...) more difficult to learn pyomo

"""
from __future__ import division

from pyomo.core import *
from pyomo.opt import SolverFactory


from EnergyAlternativesPlanning.f_model_definition import *
from EnergyAlternativesPlanning.f_model_cost_functions import *
from EnergyAlternativesPlanning.f_model_planning_constraints import *
from EnergyAlternativesPlanning.f_model_operation_constraints import *



#TODO allow to print equations with an optional parameter option
def GetElectricSystemModel_Planning(Parameters,Vars=None,EQs = {},verbose=False):
    #get_allSetsnames(model)
    # print(-1)
    model   =   Create_pyomo_model_sets_parameters(Parameters)# areaConsumption, availabilityFactor, TechParameters)
    # print(0)
    Vars=None #todo j'ai rajouté ça ici pour voir si ça bug tj lorsqu'on lance plusieurs fois d'affilée
    if Vars == None:
        model = set_Operation_variables(model, verbose=verbose)
        model = set_Planning_variables(model, verbose=verbose)
    else :
        model = math_to_pyomo_Vardef(Vars, model, verbose=verbose)
    # print(1)
    #cost function
    model   =   set_Planning_base_cost_function(model)

    EQs = {} #todo same

    if len(EQs)==0:
        model   =   set_Operation_Constraints_energyCapacityexchange(EQs,model)
    else:
        model = math_to_pyomo_constraint(EQs, model)
    # print(2)
    ## different cas pour la contrainte d'équilibre offre demande --- energyCtr_EQ
    model   =   set_Operation_Constraints_Storage(model)
    # print(2.1)
    model   =   set_Operation_Constraints_stockCtr(model)
    # print(2.2)
    model   =   set_Operation_Constraints_Ramp(model)
    # print(2.3)
    model   =   set_Operation_Constraints_flex(model)
    # print(3)
    #Planning constraints
    model   =   set_Planning_Constraints_maxminCapacityCtr(model)
    model   =   set_Planning_Constraints_storageCapacityPowerCtr(model)

    return model ;

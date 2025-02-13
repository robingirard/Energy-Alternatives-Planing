
# Optimisation of operation - One node
This folder contains 
 - operation optimisation models for one node defined in [f_operationModels.py](./f_operationModels.py). To understand the maths and learn about how to use the pyomo code, see [here](https://robingirard.github.io/Energy-Alternatives-Planning/Models/Basic_France_models/Operation_optimisation/case_operation_step_by_step_learning.html)
   - without storage in function GetElectricSystemModel_GestionSingleNode 
   - with storage in function GetElectricSystemModel_GestionSingleNode_withStorage 
 - case studies that apply these models:
   - several cases to learn step by step in [case_operation_step_by_step_learning.ipynb](./case_operation_step_by_step_learning.ipynb) (associated web page is see [here](https://robingirard.github.io/Energy-Alternatives-Planning/Models/Basic_France_models/Operation_optimisation/case_operation_step_by_step_learning.html))
   - a more detailed case of France in [case_simple_France.py](./case_simple_France.py) still simple because only one node !
 
If you are interested in **Planning** (optimisation of investment with operation constraints), you should go to Folder [Planning_optimisation](../Planning_optimisation/README.md) in the same models folder. 
If you are interested in **multi node** optimisation (of Planning and operation), you should start with the 2 nodes models [Basic_France_Germany_models](./../Basic_France_Germany_models/README.md) or you could go further with the more realistic European 7 nodes model [Seven_node_Europe](./../Seven_node_Europe/README.md). 


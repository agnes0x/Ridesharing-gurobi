import gurobipy as grb
import pandas as pd
import numpy as np

# data defined here:
bigM= 10000000
Penalty=200
F = 1.2 #max detour factor"
K = 0.3 #fix fuel cost
L = 0.2 #Blablacar price per kilometer
#TBD:
#C_i_d[i][d]=
#C_d[d]=
#A_d[d]=
#C_comp=

# Import data
inFileName = 'finaldata_english_v2.csv'
all_data = pd.read_csv(inFileName, sep=";", index_col=2) #maybe use something like header?
allPeople = all_data.index.values # .values gives us just the values without the index (row names)


# define the sets from the importd data
drivers=[]
passengers=[]
companies=[]

for pstring in allPeople:
        if "Passenger" in pstring:
            #passenger[i]=string
            passengers.append(pstring)
            
        elif "Driver" in pstring:
            drivers.append(pstring)
            
        elif "Company" in pstring:
            companies.append(pstring)
            
        else:
            raise NameError("Invalid person name")

allPeople = passengers + drivers + companies
pasComp = passengers + companies
pasDriv = passengers + drivers

# Functions
# for distance calculation from coordinates

earthRadius = 6371000

def str2num(string):
    try:
        num = float(string)
        return num
    except ValueError:
        return []
  
def deg2rad(deg):
    deg = deg * (np.pi/180.0)
    return deg

def getDistanceFromLatLonInKm(lat1,lon1,lat2,lon2):
     R = 6371 #Radius of the earth in km
     dLat = deg2rad(str2num(lat2)-str2num(lat1))
     dLon = deg2rad(str2num(lon2)-str2num(lon1)) 
     a = np.sin(dLat/2) * np.sin(dLat/2) + np.cos(deg2rad(lat1)) * np.cos(deg2rad(lat2)) * np.sin(dLon/2) * np.sin(dLon/2)
     c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a)) 
     d = R * c #Distance in km
     return d    

#do the the distance dictionary

distance_dictionary = {}

for i in allPeople:
    distance_dictionary[i]={}
    
    for j in allPeople:
       #"lat", "long" exactly as the excel column name!
       distance_dictionary[i][j] = getDistanceFromLatLonInKm(all_data.loc[i, "lat"], all_data.loc[i, "long"], all_data.loc[j, "lat"],  all_data.loc[j, "long"])
  

# Write output file
outFileName = 'output.csv'
file = open(outFileName,mode='w',encoding='utf-8-sig')
for pstring in allPeople  :
    for ppstring in allPeople:
        file.write(str(distance_dictionary[pstring][ppstring])+',')
    file.write('\n')
file.close()




## MODEL##
       
 # Create a new model
model = grb.Model("Model1")
    
 # Create variables
# 1 if passenger i is assigned to route of driver d
Y_i_d = model.addVars(passengers, drivers, vtype=grb.GRB.BINARY, name = "Y")
# 1 if route of driver d directs from location i to j
X_i_j_d = model.addVars(pasDriv, pasComp, drivers, vtype=grb.GRB.BINARY, name = "X")
#the actual price for passenger i, if he/she travels with driver d 
C_i_d = model.addVars(passengers, drivers, vtype=grb.GRB.CONTINUOUS, name = "C")
#constraints:
#C_i_d >=0

#linearization!
#binary variable for the product of Y and C
Z_i_d = model.addVars(passengers, drivers, vtype=grb.GRB.CONTINUOUS, name = "Z")
#constrints:!
# Z <=bigM * Y_i_d 
# Z <= C_i_d
# Z >= C_i_d - (1-Y_i_d)*bigM
# Z >=0


 # Set objective
expr1 = 0
#for d in range(len(drivers)):
for d in drivers:
    for i in pasDriv:
        for j in pasComp:
            expr1 += (distance_dictionary[i][j] * X_i_j_d[i, j, d])
expr2 = 0  
expr2_2=0
for i in passengers:
    for d in drivers:
        expr2_2 +=Y_i_d[i,d]           
    expr2 +=(1-expr2_2)*Penalty       
#(grb.quicksum(Y_i_d[i, d] for d in drivers)

obj = expr1 + expr2           

model.setObjective(obj, grb.GRB.MINIMIZE)

#Y_i_d[i, d].sum("*", d)
#Constraint 1
model.addConstrs(
    (grb.quicksum(Y_i_d[i, d] for i in passengers) <= all_data.loc[d, "seats"]
     	for d in drivers), "Car capacity")

#Constraint 2
model.addConstrs(
    (grb.quicksum(Y_i_d[i, d] for d in drivers) <= 1
     	for i in passengers), "Passenger assigned once")

#Constraint 3
model.addConstrs(
    (grb.quicksum(X_i_j_d[d, j, d] for j in pasComp) == 1
     	for d in drivers), "Driver must leave origin")

#Constraint 4
model.addConstrs(
    (grb.quicksum(X_i_j_d[i, j, d] for i in pasDriv for j in companies) == 1
     	for d in drivers), "Driver must arrive at companies")

#Constraint 5

#THIS WAY it WORKS (kinda)
    #GurobiError: Q matrix is not positive semi-definite (PSD)
# =============================================================================
# model.addConstrs(
#     (grb.quicksum(Z_i_d[i,d]for i in passengers) >= all_data.loc[d, "minrevenue"]
#      	for d in drivers), "Exp revenue of Driver")
# 
# =============================================================================

#Constraint 6
#THIS WAY it WORKS
model.addConstrs(
        ( Z_i_d[i,d] <= all_data.loc[i, "maxprice"]
            for i in passengers for d in drivers), "Willingness to Pay Passenger")
  



#Constraint 7
  #it works without it as well, but for future reference, how do we specify that i =/= j?
model.addConstrs(
     (grb.quicksum(X_i_j_d[i, j, d]*distance_dictionary[i][j] for i in pasDriv for j in pasComp) <= F*distance_dictionary[d][c] for d in drivers for c in companies), "Alternative way smaller than direct way")


#constraint 8
#model.addConstrs(
#    (grb.quicksum(X_i_j_d[i, j, d]*distance_dictionary*K for i,j in allPeople)  == ((grb.quicksum(C_i_d[i,d] for i in passengers))+ C_d[d] + A_d[d]+C_comp)
#     	for d in drivers), "Total cost equation from a single driver`s perspective")

#constraint 9
model.addConstrs(
    (grb.quicksum(X_i_j_d[i, j, d] for i in pasDriv if i!=j) == Y_i_d[j, d]
     	for d in drivers for j in passengers ), "If Passenger j is assigned, then only one way leading to passenger j is activated")

#constraint 10
model.addConstrs(
    (grb.quicksum(X_i_j_d[j, i, d] for i in pasComp if i!=j) == Y_i_d[j, d]
     	for d in drivers for j in passengers), "If Passenger j is assigned, then only one way starting from passenger j is activated.")


#constraint PRICE
model.addConstrs(
    (C_i_d[i, d] ==  Y_i_d[i, d]*distance_dictionary[i][b]*L for i in passengers for b in companies for d in drivers), 
        "Blabla car pricing model")

#constraint PRICE lower bounds
model.addConstrs(
    (C_i_d[i, d] >= 0 for i in passengers for d in drivers), 
     "PRICE lower bounds")

#constraint PRICE upper bounds
#model.addConstrs(
 #    (C_i_d[i, d] <= 1000 for i in passengers for d in drivers), 
  #   "Blabla car pricing model")

#constraints for linearization:
# Z <=bigM * Y_i_d 
model.addConstrs(
    (Z_i_d[i, d] <= bigM*Y_i_d[i,d] for i in passengers for d in drivers), 
     "linearization bigm")

# Z <= C_i_d
model.addConstrs(
    (Z_i_d[i, d] <= C_i_d[i,d] for i in passengers for d in drivers), 
     "linearization Cid")

# Z >= C_i_d - (1-Y_i_d)*bigM
model.addConstrs(
    (Z_i_d[i, d] >= C_i_d[i,d] - (1-Y_i_d[i,d])*bigM for i in passengers for d in drivers), 
     "linearization Cid bigm")
# Z >=0
model.addConstrs(
    (Z_i_d[i, d] >= 0 for i in passengers for d in drivers), 
     "linearization nonzero")


#force y to be 1
#model.addConstr(
#    Y_i_d["Passenger8", "Driver43"] == 1 , 
#     "force")




model.optimize()


# =============================================================================

for d in drivers:
    for i in pasDriv:
        for j in pasComp:
            if X_i_j_d[i, j, d].X >= 1:
                print ("route of driver" + d)
                print([i, j])
                print(X_i_j_d[i, j, d].X*distance_dictionary[i][j]*K)
            
a = [] 
for i in passengers:
   a.append(i)
   for j in drivers:
       if Y_i_d[i, j].X == 0:

       
           
           
# =============================================================================
# #print("Passengers who were not assigned:") 
#            #print([i, j] & "cost of passenger:" & [Z_i_d[i, j].X])
#    #print([i])
#             #print(X_i_j_d[i, j, d]*distance_dictionary[i][j]*K)
#             #print(Y_i_d[i, j].X )
#             #print(C_i_d[i, j].X )
#             #print([Z_i_d[i, j].X])
#             
# 
# #print(model.getConstrByName("Willingness to Pay Passenger"))
# 
#     
# #for i in model.getConstrs():
#  #   if i ==1
#   #      print(i)
#     
# 
# # =============================================================================
# # # do IIS
# # print('The model is infeasible; computing IIS')
# # model.computeIIS()
# # if model.IISMinimal:
# #   print('IIS is minimal\n')
# # else:
# #   print('IIS is not minimal\n')
# # print('\nThe following constraint(s) cannot be satisfied:')
# # for c in model.getConstrs():
# #     if c.IISConstr:
# #         print('%s' % c.constrName)
# #         
# # =============================================================================
#         
#         
# # =============================================================================
# #         
# # # Write output file
# # file = open(outFileName,mode='w',encoding='utf-8-sig')
# # for row in range(len(norm)):
# #     for column in range(len(norm)):
# #         file.write(str(norm[row][column])+',')
# #     file.write('\n')
# # file.close()
# # 
# # =============================================================================
# =============================================================================
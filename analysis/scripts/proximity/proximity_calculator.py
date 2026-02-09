from haversine import haversine, Unit
import numpy as np
import pandas as pd

#Import location data of NPPs
NPP_df = pd.read_excel('../../facility_data/reactors/Reactors.xlsx')

#Your current location
my_loc = (42.28305385080917, -83.70655214756565) #(Latitude, Longitude)

##Returns your distance to all NPPs in America, in miles
def getDistances(loc, df):
    distance_list = np.empty((0,2))
    for i in range(NPP_df['Name'].size):
        npp = (df['Lat'][i], df['Long'][i])
        distance = haversine(loc, npp, unit=Unit.MILES)
        name_dist = np.array([[df['Name'][i], distance]], dtype = object)
        distance_list = np.append(distance_list, name_dist, axis = 0)
    
        sorted_indices = np.argsort(distance_list[:,1])
        sorted_dist = distance_list[sorted_indices]
    return sorted_dist

##Tells you how far you are to NPPs within a given cutoff range
def distCutoffs(dist_arr, cutoff_arr):
    cutoff_arr = np.insert(cutoff_arr, 0, 0)
    for i in range(1, cutoff_arr.size):
        print("You are within", cutoff_arr[i], "miles of:")
        filtered_dist = npp_distances[(npp_distances[:,1]<cutoff_arr[i]) & 
                                      (npp_distances[:,1]>cutoff_arr[i-1])]
        for j in range(filtered_dist[:,0].size):
            print(filtered_dist[j][0], "-", np.round(filtered_dist[j][1], 2), "miles ")
        print('\n')
        
npp_distances = getDistances(my_loc, NPP_df)

#Maximum distances to filter NPP proximity 
cutoffs = np.array([10, 50]) #Any number of cutoffs, in miles

distCutoffs(npp_distances, cutoffs)




# imports

import os
import csv

# generate list of folders in data folder

path = "./data"
dir_list = os.listdir(path)
print("Loaded data folders:")
print(dir_list)

# create giant spammer list

spammers = []

for x in dir_list:
    path = f"./data/{x}/spammers.csv"
    with open(path) as csvfile:
        csv_reader = csv.reader(csvfile, delimiter=',')
        for row in csv_reader:
            if row[0] != "contract":
                spammers.append(row[0])

# remove duplicates from giant spammer list

spammer_list = []

for i in spammers:
    if i not in spammer_list:
        j = i.lower()
        spammer_list.append(j)

print("Created spammer list:")
print(spammer_list)

# load known MEVG searchers

searchers = []

path = f"./searchers.csv"
with open(path) as csvfile:
    csv_reader = csv.reader(csvfile, delimiter=',')
    for row in csv_reader:
        if row[0] != "Searchers":
            searchers.append(row[0])

print("Loaded known MEVG searchers:")
print(searchers)

# create vulnerable searcher list

vulnerable_searchers = []

for x in searchers:
    if x in spammer_list:
        vulnerable_searchers.append(x)

not_vulnerable_searchers = []

for x in searchers:
    if x not in vulnerable_searchers:
        not_vulnerable_searchers.append(x)

print("Found " + str(len(vulnerable_searchers)) + " vulnerable searchers:")
print(vulnerable_searchers)

print("Found " + str(len(not_vulnerable_searchers)) + " not vulnerable searchers:")
print(not_vulnerable_searchers)
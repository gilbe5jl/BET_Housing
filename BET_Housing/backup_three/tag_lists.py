import json
import sys
import os



with open(os.path.join(sys.path[0], 'config.json'), "r") as config_file:
    config_data = config_file.read()
    config_vars = json.loads(config_data)
tags = config_vars['tags']

def output_tag_list():
    returnList = [
        tags['LoadProgram'],
        tags['StartProgram'],
        tags['EndProgram'],
        tags['AbortProgram'],
        tags['Reset'],
        tags['PartType'],
        tags['PartProgram'],
        tags['ScanNumber'],
        tags['PUN'],
        tags['GMPartNumber'],
        tags['Module'],
        tags['PlantCode'],
        tags['Month'],
        tags['Day'],
        tags['Year'],
        tags['Hour'],
        tags['Minute'],
        tags['Second']
    ]
    return returnList

def input_tag_list(switch):
    if switch == 1:
        returnList = [
            tags['PartType'],
            tags['PartProgram'],
            tags['ScanNumber'],
            #tags['PUN'],
            'PUN',
            tags['Module'],
            tags['PlantCode'],
            tags['Month'],
            tags['Day'],
            tags['Year'],
            tags['Hour'],
            tags['Minute'],
            tags['Second'],
        ]
    elif switch == 2:
        returnList = [
            tags['PartType'],
            tags['PartProgram'],
            tags['ScanNumber'],
            #tags['PUN'],
            'PUN',
            tags['Module'],
            tags['PlantCode'],
            tags['Month'],
            tags['Day'],
            tags['Year'],
            tags['Hour'],
            tags['Minute'],
            tags['Second'],
            tags['Busy'],
            tags['Done']
        ]
    return returnList

def result_tag_list(): 
    returnList = [
        
        'DefectNumber',
        'DefectSize',
        'DefectZone',
        'Pass',
        'Fail',
        'MaskFail',
        'SizeFail',
        'SpacingFail',
        'DensityFail'
    ]
    return returnList

def fault_tag_list():
    returnList = [
        tags['Faulted'],
        tags['PhoenixFltCode'],
        tags['KeyenceFltCode']
    ]
    return returnList

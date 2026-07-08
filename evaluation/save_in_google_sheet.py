import pygsheets

client = pygsheets.authorize(client_secret='C:/Users/admin/Desktop/STREAMING_FAIRNESS_RESULTS/client_secret_429912033775-lrpact4bafhd4s8ra9s4ieejp3hsu1ri.apps.googleusercontent.com.json')
# Open the spreadsheet and the first sheet.
sh = client.open('FairnessResults - TREATS (DITTO/GNEM)')
wks = sh.worksheet(property='index', value=0)

print("List of sheets: ", sh.worksheets())



results = {'top-5': [1.0, 1.0, 1.0, 1.0], 'top-10': [0.9, 0.9, 0.9, 0.9], 'top-15': [0.8666666666666667, 0.9333333333333333, 0.9333333333333333, 0.9333333333333333], 'top-20': [0.8, 0.9, 0.9, 0.85], 'time_to_match': [13.31139612197876, 10.712061405181885, 9.778184652328491, 8.827579021453857], 'time_to_rank': [0.12263607978820801, 0.021471023559570312, 0.009545087814331055, 0.014573097229003906], 'total_time': [13.434032201766968, 10.733532428741455, 9.787729740142822, 8.842152118682861], 'PPVP': [0.15625, 0.09999999999999998, 0.09999999999999998, 0.15000000000000002], 'TPRP': [0.0, 0.09999999999999998, 0.09999999999999998, 0.15000000000000002], 'Bias': [0.2, 0.0, 0.0, 0.0]}




letter = 'X'
number = '38'
back = ''
n = 0
for key in results:
    cell_reference = back + letter + number
    print(cell_reference)
    wks.update_values(crange=cell_reference, values=[results[key]], majordim='COLUMNS')

    letter = chr(ord(letter) + 1)
    if letter > "Z":
        back = 'A'
        letter = 'A'
        n += 1



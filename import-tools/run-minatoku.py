#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os
import sys
import xlrd
import json

in_path = sys.argv[1]
out_path = sys.argv[2]

book = xlrd.open_workbook(in_path)
sheet = book.sheet_by_index(0)
rows = sheet.nrows
cols = sheet.ncols

j = {}

current_shop = 'Starbucks'
for i in range(rows):
    firstrow = sheet.cell(i,0).value
    lon = sheet.cell(i,1).value
    lat = sheet.cell(i,2).value
    okng = sheet.cell(i,3).value

    print okng

    if okng == '' and firstrow != '':
        current_shop = firstrow.replace('  location sample','')
    if okng != 'OK': continue

    j[str(i)] = [current_shop,lon,lat]

with open(out_path,'w') as fw:
    fw.write(json.dumps(j))

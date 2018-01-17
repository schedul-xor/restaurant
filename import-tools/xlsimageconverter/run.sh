#!/usr/bin/sh

#python run-bangkok.py list-bangkok.xlsx out-bangkok.json
#python run-minatoku.py list-minatoku.xlsx out-minatoku.json
#python run-morebangkok.py list-morebangkok.xlsx out-morebangkok.json
java -jar build/libs/xlsimageconverter-all-1.0-SNAPSHOT.jar ../list-patentecho.xlsx ../out-patentecho.json

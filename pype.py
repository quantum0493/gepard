#!/usr/bin/env python

import shelve

import Model, Approach, Fitter
import utils 
import plots

#from results import *

# [1] Load experimental data and theoretical models

data = utils.loaddata('data/ep2epgamma')  # dictionary {1 : DataSet instance, ...}
db = shelve.open('theories.db', 'r')

## some shortcuts
#DMGLO = db['DMGLO']
#DMGLO1 = db['DMGLO1']
#KKGLO = db['KKGLO']
#KKGLO1 = db['KKGLO1']
#NN1 = db['NN1']


## [2] Choose subset of datapoints for fitting

GLOpoints = data[32][12:] + data[8] + data[29]  # DM's GLO set
GLO1points = data[31][12:] + data[8] + data[29] + data[30]  # DM's GLO1 set
fitpoints = data[31][12:14] + data[8][1:3] + data[30][2:4]  # test set
HA17 = utils.select(data[34], criteria=['t == -0.17'])
HA33 = utils.select(data[34], criteria=['t == -0.33'])
#fitpoints = GLO1points + 6*data[30]
fitpoints = GLO1points
#fitpoints = data[5]

## [3] Create a theory

m = Model.ModelNN(output_layer=['ImH', 'ReH', 'ReHt'])
t = Approach.hotfixedBMK(m)

#m = Model.ModelDR()
#m.parameters.update(DMGLO)
#t = Approach.hotfixedBMK(m)
#t.name = 'DMGLO'
#t.description = 'DM fit to HERMES and CLAS BSA/BCA data. Only CFF H.'
#t.save(db)
#del m, t

#m = Model.ModelDR()
#m.parameters.update(DMGLO1)
#t = Approach.hotfixedBMK(m)
#t.name = 'DMGLO1'
#t.description = 'DM fit to HERMES and CLAS BSA/BCA data, and HALL-A. With large CFF Htilde'
#t.save(db)
#db['DMGLO1'] = t
#del m, t

#db.close()

## [4] Do the fit

#t = db['DMGLO'].copy()
#t.model.release_parameters('bS', 'rv', 'bv', 'C', 'MC') #, 'trv')
#f = Fitter.FitterMinuit(GLOpoints, t)

f = Fitter.FitterBrain(fitpoints, t)

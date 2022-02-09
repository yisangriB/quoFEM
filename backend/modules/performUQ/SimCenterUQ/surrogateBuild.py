import time
import shutil
import os
import sys
import subprocess
import math
import pickle
import glob
import json
from copy import deepcopy
import warnings
import copy
import random
import matplotlib

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)

from UQengine import UQengine
# import pip installed modules

try:
    moduleName = "emukit"
    import emukit.multi_fidelity as emf
    from emukit.model_wrappers.gpy_model_wrappers import GPyMultiOutputWrapper
    from emukit.multi_fidelity.convert_lists_to_array import convert_x_list_to_array, convert_xy_lists_to_arrays
    moduleName = "pyDOE"
    from pyDOE import lhs
    moduleName = "GPy"
    import GPy as GPy
    moduleName = "scipy"
    from scipy.stats import lognorm, norm
    moduleName = "numpy"
    import numpy as np
    moduleName = "UQengine"
    #from utilities import run_FEM_batch, errorLog
    error_tag=False # global variable
except:
    error_tag=True 
    print("Failed to import module:" + moduleName)

## Main function

def main(inputArgs):
    gp = surrogate(inputArgs)

class surrogate(UQengine):

    def __init__(self, inputArgs):
        super(surrogate, self).__init__(inputArgs)
        t_init = time.time()

        if error_tag == True:
            if self.os_type.lower().startswith('win'):
                msg = 'Failed to load python module [' + moduleName + ']. Go to <File-Preference-Python> and reset the path.'
            else:
                msg = 'Failed to load python module [' + moduleName + ']. Did you forget <pip3 install nheri_simcenter --upgrade>?'
            self.exit(msg)

        self.cleanup_workdir()

        #
        # Read Json File
        #

        self.readJson()

        #
        # Create GP wrapper
        #

        self.create_gp_model()

        #
        # run DoE
        #
        self.train_surrogate(t_init)

        #
        # save model
        #

        self.save_model('SimGpModel')


    def readJson(self):

        try:
            with open(self.work_dir + '/templatedir/dakota.json') as f:
                dakotaJson = json.load(f)
        except ValueError:
            msg = 'invalid json format - dakota.json'
            self.exit(msg)
        if dakotaJson['UQ_Method']['uqType'] != 'Train GP Surrogate Model':
            msg = 'UQ type inconsistency : user wanted <' + dakotaJson['UQ_Method'][
                'uqType'] + '> but we called <Global Surrogate Modeling> program'
            self.exit(msg)

        surrogateJson = dakotaJson["UQ_Method"]["surrogateMethodInfo"]

        #
        #  common for all surrogate options
        #

        self.rv_name = list()
        x_dim = 0

        for rv in dakotaJson['randomVariables']:
            self.rv_name += [rv['name']]
            x_dim += 1

        self.g_name = list()
        y_dim = 0
        for g in dakotaJson['EDP']:
            # scalar
            if g['length'] == 1:
                self.g_name += [g['name']]
                y_dim += 1
            # vector
            else:
                for nl in range(g['length']):
                    self.g_name += ["{}_{}".format(g['name'], nl+1)]
                    y_dim += 1

        if x_dim == 0:
            msg = 'Error reading json: RV is empty'
            self.exit(msg)

        if y_dim == 0:
            msg = 'Error reading json: EDP(QoI) is empty'
            self.exit(msg)

        do_predictive = False
        automate_doe = False


        self.x_dim = x_dim
        self.y_dim = y_dim
        self.do_predictive = do_predictive


        try:
            self.do_parallel = surrogateJson["parallelExecution"]
        except:
            self.do_parallel = True

        if self.do_parallel:
            self.n_processor, self.pool = self.make_pool()
            self.cal_interval = self.n_processor
        else:
            self.n_processor = 1
            self.pool = 0
            self.cal_interval = 5
        print("self.cal_interval : {}".format(self.cal_interval))

        #
        #  Advanced
        #

        self.do_logtransform = surrogateJson["logTransform"]
        self.kernel = surrogateJson["kernel"]
        self.do_linear = surrogateJson["linear"]
        self.nugget_opt = surrogateJson["nuggetOpt"]

        if surrogateJson["advancedOpt"]:
            try:
                self.nuggetVal = np.array(json.loads("[{}]".format(surrogateJson["nuggetString"])))
            except json.decoder.JSONDecodeError:
                msg = 'Error reading json: improper format of nugget values/bounds. Provide nugget values/bounds of each QoI with comma delimiter'
                self.exit(msg)

            if self.nuggetVal.shape[0]!=self.y_dim and self.nuggetVal.shape[0]!=0 :
                msg = 'Error reading json: Number of nugget quantities ({}) does not match # QoIs ({})'.format(self.nuggetVal.shape[0],self.y_dim)
                self.exit(msg)

            if self.nugget_opt == "Fixed Values":
                for Vals in self.nuggetVal:
                    if (not np.isscalar(Vals)):
                        msg = 'Error reading json: provide nugget values of each QoI with comma delimiter'
                        self.exit(msg)

            elif self.nugget_opt == "Fixed Bounds":
                for Bous in self.nuggetVal:
                    if (np.isscalar(Bous)):
                        msg = 'Error reading json: provide nugget bounds of each QoI in brackets with comma delimiter, e.g. [0.0,1.0],[0.0,2.0],...'
                        self.exit(msg)
                    elif (isinstance(Bous,list)):
                        msg = 'Error reading json: provide both lower and upper bounds of nugget'
                        self.exit(msg)
                    elif Bous.shape[0]!=2:
                        msg = 'Error reading json: provide nugget bounds of each QoI in brackets with comma delimiter, e.g. [0.0,1.0],[0.0,2.0],...'
                        self.exit(msg)
                    elif Bous[0]>Bous[1]:
                        msg = 'Error reading json: the lower bound of a nugget value should be smaller than its upper bound'
                        self.exit(msg)
        else:
            pass
            # use default
            # self.do_logtransform = False
            # self.kernel = 'Matern 5/2'
            # self.do_linear = False
            # self.nugget_opt = "optimize"

        # Save model information
        if (surrogateJson["method"] == "Sampling and Simulation") or (surrogateJson["method"] == "Import Data File"):
            self.do_mf=False
            self.modelInfoHF = model_info(surrogateJson, dakotaJson['randomVariables'], self.work_dir, x_dim, y_dim, self.errfile, self.n_processor, idx=0)
            self.modelInfoLF = model_info(surrogateJson, dakotaJson['randomVariables'], self.work_dir, x_dim, y_dim, self.errfile, self.n_processor, idx=-1) # NONE model
        elif surrogateJson["method"] == "Import Multi-fidelity Data File":
            self.do_mf=True
            self.modelInfoHF = model_info(surrogateJson["highFidelity"], dakotaJson['randomVariables'], self.work_dir, x_dim, y_dim, self.errfile,self.n_processor,  idx=1)
            self.modelInfoLF = model_info(surrogateJson["lowFidelity"], dakotaJson['randomVariables'], self.work_dir, x_dim, y_dim, self.errfile,self.n_processor,  idx=2)
        else:
            msg = 'Error reading json: select among "Import Data File", "Sampling and Simulation" or "Import Multi-fidelity Data File"'
            self.exit(msg)

        if self.modelInfoHF.is_model:
            self.ll = self.modelInfoHF.ll
            self.doe_method = self.modelInfoHF.doe_method
            self.thr_NRMSE = self.modelInfoHF.thr_NRMSE
            self.thr_t = self.modelInfoHF.thr_t
        elif self.modelInfoLF.is_model:
            self.ll = self.modelInfoLF.ll
            self.doe_method = self.modelInfoLF.doe_method
            self.thr_NRMSE = self.modelInfoLF.thr_NRMSE
            self.thr_t = self.modelInfoLF.thr_t
        elif self.modelInfoHF.is_data:
            self.ll = self.modelInfoHF.ll
            self.doe_method = self.modelInfoLF.doe_method # whatever.
            self.thr_NRMSE = self.modelInfoLF.thr_NRMSE # whatever.
            self.thr_t = self.modelInfoLF.thr_t # whatever.
        else:
            self.ll = self.modelInfoLF.ll # whatever.
            self.doe_method = self.modelInfoLF.doe_method # whatever.
            self.thr_NRMSE = self.modelInfoLF.thr_NRMSE # whatever.
            self.thr_t = self.modelInfoLF.thr_t # whatever.


        self.modelInfoHF.runIdx = 0
        self.modelInfoLF.runIdx = 0
        if self.modelInfoHF.is_model and self.modelInfoLF.is_model:
            self.doeIdx = "HFLF"
            self.modelInfoHF.runIdx = 1
            self.modelInfoLF.runIdx = 2
            self.cal_interval = 1
        elif not self.modelInfoHF.is_model and self.modelInfoLF.is_model:
            self.doeIdx = "LF"
        elif self.modelInfoHF.is_model and not self.modelInfoLF.is_model:
            self.doeIdx = "HF"
        else:
            self.doeIdx = "HF" # whatever.

        #
        # For later use..
        #
        self.femInfo = dakotaJson["fem"]
        #surrogateJson["fem"] = dakotaJson["fem"]

        self.rvName = []
        self.rvDist = []
        self.rvVal = []
        for nx in range(x_dim):
            rvInfo = dakotaJson["randomVariables"][nx]
            self.rvName = self.rvName + [rvInfo["name"]]
            self.rvDist = self.rvDist + [rvInfo["distribution"]]
            if self.modelInfoHF.is_model:
                self.rvVal = self.rvVal + [(rvInfo["upperbound"] + rvInfo["lowerbound"]) / 2]
            elif self.modelInfoHF.is_data:
                self.rvVal = self.rvVal + [np.mean(self.modelInfoHF.X_existing[:, nx])]
            else:
                self.rvVal = [0] * self.x_dim

    def create_gp_model(self):
        kernel = self.kernel
        x_dim = self.x_dim
        y_dim = self.y_dim

        # choose kernel
        if kernel == 'Radial Basis':
            kr = GPy.kern.RBF(input_dim=x_dim, ARD=True)
        elif kernel == 'Exponential':
            kr = GPy.kern.Exponential(input_dim=x_dim, ARD=True)
        elif kernel == 'Matern 3/2':
            kr = GPy.kern.Matern32(input_dim=x_dim, ARD=True)
        elif kernel == 'Matern 5/2':
            kr = GPy.kern.Matern52(input_dim=x_dim, ARD=True)
        else:
            msg = 'Error running SimCenterUQ - Kernel name <{}> not supported'.format(kernel)
            self.self.exit(msg)
        if self.do_linear:
            kr = kr + GPy.kern.Linear(input_dim=x_dim, ARD=True)

        X_dummy = np.zeros((1,x_dim))
        Y_dummy = np.zeros((1,y_dim))
        # for single fidelity case
        if not self.do_mf:
            kg = kr
            self.m_list = list()
            for i in range(y_dim):
                self.m_list = self.m_list + [GPy.models.GPRegression(X_dummy, Y_dummy, kernel=kg.copy(),normalizer=True)]
                for parname in self.m_list[i].parameter_names():
                    if parname.endswith('lengthscale'):
                        exec('self.m_list[i].' + parname + '=self.ll')

        # for multi fidelity case
        else:
            kgs = emf.kernels.LinearMultiFidelityKernel([kr.copy(), kr.copy()])
            X_list, Y_list = emf.convert_lists_to_array.convert_xy_lists_to_arrays([X_dummy, X_dummy], [Y_dummy, Y_dummy])

            self.m_list = list()
            for i in range(y_dim):
                self.m_list = self.m_list + [GPyMultiOutputWrapper(emf.models.GPyLinearMultiFidelityModel(X_list, Y_list, kernel=kgs.copy(), n_fidelities=2), 2, n_optimization_restarts=15)]

        self.x_dim = x_dim
        self.y_dim = y_dim


        self.nc1 = min(200 * x_dim, 2000)  # candidate points
        self.nq = min(200 * x_dim, 2000)  # integration points


    def predict(self,m_tmp,X):


        if not self.do_mf:

            if all(m_tmp.Y == np.mean(m_tmp.Y, axis=0)):
                return m_tmp.Y[0], 0 # if response is constant - just return constant
            else:
                return m_tmp.predict(X)
        else:

            idxHF = np.argwhere(m_tmp.gpy_model.X[:, -1] == 0)
            if all(m_tmp.gpy_model.Y == np.mean(m_tmp.gpy_model.Y[idxHF,:], axis=0)):
                return m_tmp.gpy_model.Y[0], 0 # if high-fidelity response is constant - just return constant
            else:
                X_list = convert_x_list_to_array([X, X])
                X_list_h = X_list[X.shape[0]:]
                return m_tmp.predict(X_list_h)

    def set_XY(self,m_tmp,X_hf,Y_hf,X_lf=float("nan"),Y_lf=float("nan")):

        if self.do_logtransform:
            if np.min(Y_hf) < 0:
                msg = 'Error running SimCenterUQ - Response contains negative values. Please uncheck the log-transform option in the UQ tab'
                self.self.exit(msg)
            Y_hfs = np.log(Y_hf)
        else:
            Y_hfs = Y_hf

        if self.do_logtransform and self.do_mf:
            if np.min(Y_lf) < 0:
                msg = 'Error running SimCenterUQ - Response contains negative values. Please uncheck the log-transform option in the UQ tab'
                self.self.exit(msg)
            Y_lfs = np.log(Y_lf)
        else:
            Y_lfs = Y_lf

        # # below is dummy
        # if np.all(np.isnan(X_lf)) and np.all(np.isnan(Y_lf)):
        #     X_lf = self.X_lf
        #     Y_lfs = self.Y_lf

        if not self.do_mf:
            m_tmp.set_XY(X_hf, Y_hfs)
        else:
            X_list_tmp, Y_list_tmp = emf.convert_lists_to_array.convert_xy_lists_to_arrays([X_hf, X_lf],[Y_hfs, Y_lfs])
            m_tmp.set_data(X=X_list_tmp,Y=Y_list_tmp)

        return m_tmp

    def setNugget(self, m_tmp, nugget_opt_tmp, ny):

        if not self.do_mf:
            if nugget_opt_tmp == "Optimize":
                m_tmp['Gaussian_noise.variance'].unfix()
            elif nugget_opt_tmp == "Fixed Values":
                m_tmp['Gaussian_noise.variance'].constrain_fixed(self.nuggetVal[ny])
            elif nugget_opt_tmp == "Fixed Bounds":
                m_tmp['Gaussian_noise.variance'].constrain_bounded(self.nuggetVal[ny][0], self.nuggetVal[ny][1])
            elif nugget_opt_tmp == "Zero":
                m_tmp['Gaussian_noise.variance'].constrain_fixed(0)

        if self.do_mf:
            # TODO: is this right?
            if nugget_opt_tmp == "Optimize":
                m_tmp.gpy_model.mixed_noise.Gaussian_noise.unfix()
                m_tmp.gpy_model.mixed_noise.Gaussian_noise_1.unfix()

            elif nugget_opt_tmp == "Fixed Values":
                # m_tmp.gpy_model.mixed_noise.Gaussian_noise.constrain_fixed(self.nuggetVal[ny])
                # m_tmp.gpy_model.mixed_noise.Gaussian_noise_1.constrain_fixed(self.nuggetVal[ny])
                msg = 'Currently Nugget Fixed Values option is not supported'
                self.self.exit(msg)
                
            elif nugget_opt_tmp == "Fixed Bounds":
                # m_tmp.gpy_model.mixed_noise.Gaussian_noise.constrain_bounded(self.nuggetVal[ny][0],
                #                                                                       self.nuggetVal[ny][1])
                # m_tmp.gpy_model.mixed_noise.Gaussian_noise_1.constrain_bounded(self.nuggetVal[ny][0],
                #                                                                         self.nuggetVal[ny][1])
                msg = 'Currently Nugget Fixed Bounds option is not supported'
                self.self.exit(msg)
            elif nugget_opt_tmp == "Zero":
                m_tmp.gpy_model.mixed_noise.Gaussian_noise.constrain_fixed(0)
                m_tmp.gpy_model.mixed_noise.Gaussian_noise_1.constrain_fixed(0)
        return m_tmp

    def calibrate(self):
        warnings.filterwarnings("ignore")
        t_opt = time.time()
        nugget_opt_tmp = self.nugget_opt
        for ny in range(self.y_dim):
            print("y dimension {}:".format(ny))
            if not self.do_mf:
                nopt = 10
                m_tmp = copy.deepcopy(self.m_list[ny])

                # Save the previous optimal

                init_length_params={}
                for parname in m_tmp.parameter_names():
                    if parname.endswith('lengthscale'):
                        exec('init_length_params["' + parname.replace('.','_') + '"] = m_tmp.' + parname )

                # if response is constant....

                if np.var(m_tmp.Y) == 0:
                    nugget_opt_tmp = "Zero"
                    for parname in m_tmp.parameter_names():
                        if parname.endswith('variance'):
                            m_tmp[parname].constrain_fixed(0)

                # optimization #1 with previous optimal

                m_tmp = self.setNugget(m_tmp, nugget_opt_tmp, ny) # set nugget
                m_tmp.optimize(clear_after_finish=True)           # optimize parameters
                max_log_likli = m_tmp.log_likelihood()

                id_opt = 1
                print('{} among {} Log-Likelihood: {}'.format(1, nopt, m_tmp.log_likelihood()))
                m_opt = m_tmp.copy() #candidate

                # optimization #2 with bounds

                for parname in m_tmp.parameter_names():
                    if parname.endswith('lengthscale'):
                        exec('m_tmp.' + parname + '=self.ll')
                m_tmp.optimize(clear_after_finish=True)

                #check if it is better
                if m_tmp.log_likelihood() > max_log_likli:
                    max_log_likli = m_tmp.log_likelihood()
                    m_opt = m_tmp.copy()
                    id_opt = 2

                print('{} among {} Log-Likelihood: {}'.format(2, nopt, m_tmp.log_likelihood()))

                #
                # optimization #3-nopt with random inits
                #

                for no in range(nopt - 2):
                    for parname in m_tmp.parameter_names():
                        if parname.endswith('lengthscale'):
                            if math.isnan(m_opt.log_likelihood()):
                                exec('m_tmp.' + parname + '=np.random.exponential(1, (1, self.x_dim)) * init_length_params["' + parname.replace('_','.') +'"]')
                            else:
                                exec('m_tmp.' + parname + '=np.random.exponential(1, (1, self.x_dim)) * m_opt.' + parname)

                    try:
                        #m_tmp = self.setNugget(m_tmp, nugget_opt_tmp, ny)
                        m_tmp.optimize()
                    except Exception as ex:
                        print("OS error: {0}".format(ex))
                    print('{} among {} Log-Likelihood: {}'.format(no + 3, nopt, m_tmp.log_likelihood()))

                    if m_tmp.log_likelihood() > max_log_likli:
                        max_log_likli = m_tmp.log_likelihood()
                        m_opt = m_tmp.copy()
                        id_opt = no

                if math.isinf(-max_log_likli) or math.isnan(-max_log_likli):
                    if np.var(m_tmp.Y) != 0:
                        msg = "Error GP optimization failed for QoI #{}".format(ny+1)
                        self.self.exit(msg)



                print(m_opt)
                self.m_list[ny] = m_opt# overwirte
                self.calib_time = (time.time() - t_opt) * round(10 / nopt)
                print('     Calibration time: {:.2f} s, id_opt={}'.format(self.calib_time, id_opt))

            else:
                self.m_list[ny] = self.setNugget( self.m_list[ny], nugget_opt_tmp, ny)
                self.m_list[ny].optimize()
                self.calib_time = (time.time() - t_opt)
                print('     Calibration time: {:.2f} s'.format(self.calib_time))

        Y_preds, Y_pred_vars, e2 = self.get_cross_validation_err()

        return  Y_preds, Y_pred_vars, e2


    def train_surrogate(self, t_init):
        # FEM index
        self.id_sim_hf = 0
        self.id_sim_lf = 0
        self.time_hf_tot = 0
        self.time_lf_tot = 0
        self.time_hf_avg = float("Inf")
        self.time_lf_avg = float("Inf")
        self.time_ratio = 1


        x_dim = self.x_dim
        y_dim = self.y_dim

        #
        # Generate initial Samples
        #

        model_hf = self.modelInfoHF
        model_lf = self.modelInfoLF

        self.set_FEM(self.rv_name, self.do_parallel, self.y_dim, t_init, model_hf.thr_t)

        def FEM_batch_hf(X,id_sim):
            tmp =time.time()
            if model_hf.is_model:
                res = self.run_FEM_batch(X, id_sim, runIdx=model_hf.runIdx)
            else:
                res =  np.zeros((0, self.x_dim)), np.zeros((0, self.y_dim)), id_sim
            self.time_hf_tot += time.time() - tmp
            self.time_hf_avg = np.float64(self.time_hf_tot)/res[2] # so that it gives inf when divided by zero
            self.time_ratio = self.time_hf_avg/self.time_lf_avg
            return res

        def FEM_batch_lf(X,id_sim):
            tmp =time.time()
            if model_lf.is_model:
                res = self.run_FEM_batch(X, id_sim, runIdx=model_lf.runIdx)
            else:
                res =  np.zeros((0, self.x_dim)), np.zeros((0, self.y_dim)), id_sim
            self.time_lf_tot += time.time() - tmp
            self.time_lf_avg = np.float64(self.time_lf_tot)/res[2] # so that it gives inf when divided by zero
            self.time_ratio = self.time_hf_avg/self.time_lf_avg
            return res

        tmp = time.time()

        X_hf_tmp = model_hf.sampling(max([model_hf.n_init - model_hf.n_existing,0]))

        # if X is from a data file & Y is from simulation
        if model_hf.model_without_sampling:
            X_hf_tmp, model_hf.X_existing = model_hf.X_existing, X_hf_tmp
        X_hf_tmp, Y_hf_tmp, self.id_sim_hf = FEM_batch_hf(X_hf_tmp, self.id_sim_hf)

        self.X_hf, self.Y_hf = np.vstack([model_hf.X_existing, X_hf_tmp]), np.vstack([model_hf.Y_existing, Y_hf_tmp])

        X_lf_tmp = model_lf.sampling(max([model_lf.n_init - model_lf.n_existing, 0]))

        # Design of experiments - Nearest neighbor sampling
        # Giselle Fernández-Godino, M., Park, C., Kim, N. H., & Haftka, R. T. (2019). Issues in deciding whether to use multifidelity surrogates. AIAA Journal, 57(5), 2039-2054.
        self.n_LFHFoverlap=0
        new_x_lf_tmp = np.zeros((0,self.x_dim))
        X_tmp =X_lf_tmp

        for x_hf in self.X_hf:
            if X_tmp.shape[0] > 0:
                id = closest_node(x_hf, X_tmp, self.ll)
                new_x_lf_tmp = np.vstack([new_x_lf_tmp, x_hf])
                X_tmp = np.delete(X_tmp, id, axis=0)
                self.n_LFHFoverlap +=1

        new_x_lf_tmp = np.vstack([new_x_lf_tmp,X_tmp])
        new_x_lf_tmp, new_y_lf_tmp, self.id_sim_lf =FEM_batch_lf(new_x_lf_tmp, self.id_sim_lf)

        self.X_lf, self.Y_lf = np.vstack([model_lf.X_existing, new_x_lf_tmp]), np.vstack([model_lf.Y_existing, new_y_lf_tmp])

        if self.X_hf.shape[1] != self.X_lf.shape[1]:
            msg = 'Error importing input data: dimension inconsistent: high fidelity model have {} RV(s) but low fidelity model have {}.'.format(
                self.X_hf.shape[1], self.X_lf.shape[1])
            self.exit(msg)

        if self.Y_hf.shape[1] != self.Y_lf.shape[1]:
            msg = 'Error importing input data: dimension inconsistent: high fidelity model have {} QoI(s) but low fidelity model have {}.'.format(
                self.Y_hf.shape[1], self.Y_lf.shape[1])
            self.exit(msg)


        for i in range(y_dim):
            self.set_XY(self.m_list[i],self.X_hf, self.Y_hf[:, i][np.newaxis].transpose(),self.X_lf, self.Y_lf[:, i][np.newaxis].transpose()) # log-transform is inside set_XY

        #
        # Verification measures
        #

        self.NRMSE_hist = np.zeros((1, y_dim), float)
        self.NRMSE_idx = np.zeros((1, 1), int)

        print("======== RUNNING GP DoE ===========")

        exit_flag = False
        nc1 = self.nc1
        nq = self.nq
        n_new = 0
        while exit_flag == False:
            # Initial calibration

            # Calibrate self.m_list
            self.Y_cvs, self.Y_cv_vars, e2 = self.calibrate()
            if self.do_logtransform:
                #self.Y_cv = np.exp(2*self.Y_cvs+self.Y_cv_vars)*(np.exp(self.Y_cv_vars)-1) # in linear space
                # TODO: Let us use median instead of mean?
                self.Y_cv = np.exp(self.Y_cvs)
                self.Y_cv_var = np.exp(2*self.Y_cvs+self.Y_cv_vars)*(np.exp(self.Y_cv_vars)-1) # in linear space
            else:
                self.Y_cv =self.Y_cvs
                self.Y_cv_var=self.Y_cv_vars

            if self.id_sim_hf < model_hf.thr_count:
                [x_new_hf, y_idx_hf, score_hf] = self.run_design_of_experiments(nc1, nq, e2, "HFHF")
            else:
                score_hf = 0

            if self.id_sim_lf < model_lf.thr_count:
                [x_new_lf, y_idx_lf, score_lf] = self.run_design_of_experiments(nc1, nq, e2, "LF")
            else:
                score_lf = 0 #score : reduced amount of variance

            if self.doeIdx == "HFLF":
                fideilityIdx = np.argmax([score_hf/self.time_hf_avg, score_lf/self.time_lf_avg])
                if fideilityIdx==0:
                    tmp_doeIdx = "HF"
                else:
                    tmp_doeIdx = "LF"
            else:
                tmp_doeIdx = self.doeIdx

            if self.do_logtransform:
                Y_hfs = np.log(self.Y_hf)
            else:
                Y_hfs = self.Y_hf

            NRMSE_val = self.normalized_mean_sq_error(self.Y_cvs, Y_hfs)
            self.NRMSE_hist = np.vstack((self.NRMSE_hist, np.array(NRMSE_val)))
            self.NRMSE_idx = np.vstack((self.NRMSE_idx, i))

            if self.id_sim_hf >= model_hf.thr_count and self.id_sim_lf >= model_lf.thr_count:
                n_iter = i
                self.exit_code = 'count'
                if self.id_sim_hf==0 and self.id_sim_lf==0:
                    self.exit_code = 'data'
                exit_flag = True
                break

            if np.max(NRMSE_val) < model_hf.thr_NRMSE:
                n_iter = i
                self.exit_code = 'accuracy'
                exit_flag = True
                break

            if time.time() - t_init > model_hf.thr_t - self.calib_time:
                n_iter = i
                self.exit_code = 'time'
                doe_off = True
                break



            if tmp_doeIdx.startswith("HF"):
                n_new = x_new_hf.shape[0]
                if n_new + self.id_sim_hf > model_hf.thr_count:
                    n_new = model_hf.thr_count - self.id_sim_hf
                    x_new_hf = x_new_hf[0:n_new, :]
                x_hf_new, y_hf_new, self.id_sim_hf = FEM_batch_hf(x_new_hf, self.id_sim_hf)
                self.X_hf = np.vstack([self.X_hf, x_hf_new])
                self.Y_hf = np.vstack([self.Y_hf, y_hf_new])
                i = self.id_sim_hf + n_new
                
            if tmp_doeIdx.startswith("LF"):
                n_new = x_new_lf.shape[0]
                if n_new + self.id_sim_lf > model_lf.thr_count:
                    n_new = model_lf.thr_count - self.id_sim_lf
                    x_new_lf = x_new_lf[0:n_new, :]
                x_lf_new, y_lf_new, self.id_sim_lf = FEM_batch_lf(x_new_lf, self.id_sim_lf)
                self.X_lf = np.vstack([self.X_lf, x_lf_new])
                self.Y_lf = np.vstack([self.Y_lf, y_lf_new])
                i = self.id_sim_lf + n_new
                #TODO


            #print(">> {:.2f} s".format(time.time() - t_init))

            for ny in range(self.y_dim):
                self.set_XY(self.m_list[ny], self.X_hf, self.Y_hf[:, ny][np.newaxis].transpose(), self.X_lf,
                            self.Y_lf[:, ny][np.newaxis].transpose())  # log-transform is inside set_XY

        self.sim_time = time.time() - t_init
        self.NRMSE_val = NRMSE_val

        self.verify()

        print('my exit code = {}'.format(self.exit_code))
        print('1. count = {}'.format(self.id_sim_hf))
        print('2. max(NRMSE) = {}'.format(np.max(self.NRMSE_val)))
        print('3. time = {:.2f} s'.format(self.sim_time))

        '''
        import matplotlib.pyplot as plt
        dof=0
        plt.plot(self.Y_cv[:,dof],self.Y_hf[:,dof],'x');
        plt.plot(self.Y_hf[:,dof],self.Y_hf[:,dof],'-');
        plt.xlabel("CV")
        plt.ylabel("Exact")
        plt.show()
        '''
        # plt.show()
        # plt.plot(self.Y_cv[:, 1],Y_exact[:,1],'x')
        # plt.plot(Y_exact[:, 1],Y_exact[:, 1],'x')
        # plt.xlabel("CV")
        # plt.ylabel("Exact")
        # plt.show()
        #
        # self.m_list = list()
        # for i in range(y_dim):
        #     self.m_list = self.m_list + [GPy.models.GPRegression(self.X_hf, self.Y_hf, kernel=GPy.kern.RBF(input_dim=x_dim, ARD=True), normalizer=True)]
        #     self.m_list[i].optimize()
        #
        # self.m_list[i].predict()

    def verify(self):
        Y_cv = self.Y_cv
        Y = self.Y_hf
        model_hf = self.modelInfoHF

        if model_hf.is_model:
            n_err = 1000
            Xerr = model_hf.sampling(n_err)

            y_pred_var = np.zeros((n_err, self.y_dim))
            y_data_var = np.zeros((n_err, self.y_dim))

            for ny in range(self.y_dim):
                m_tmp = self.m_list[ny]
                y_data_var[:, ny] = np.var(Y[:, ny])
                # if self.do_logtransform:
                #     log_mean = np.mean(np.log(Y[:, ny]))
                #     log_var = np.var(np.log(Y[:, ny]))
                #     y_var_vals = np.exp(2*log_mean+log_var)*(np.exp(log_var)-1) # in linear space
                # else:
                #     y_var_vals = np.var(Y[:, ny])

                for ns in range(n_err):
                    y_preds, y_pred_vars = self.predict(m_tmp,Xerr[ns, :][np.newaxis])
                    if self.do_logtransform:
                         y_pred_var[ns, ny] = np.exp(2 * y_preds + y_pred_vars) * (np.exp(y_pred_vars) - 1)
                    else:
                        y_pred_var[ns, ny] = y_pred_vars


            error_ratio2_Pr = (y_pred_var / y_data_var)
            print(np.max(error_ratio2_Pr, axis=0))

            perc_thr_tmp = np.hstack([np.array([1]), np.arange(10, 1000, 50), np.array([999])])
            error_sorted = np.sort(np.max(error_ratio2_Pr, axis=1), axis=0)
            self.perc_val = error_sorted[perc_thr_tmp]  # criteria
            self.perc_thr = 1 - (perc_thr_tmp) * 0.001  # ratio=simulation/sampling

            self.perc_thr = self.perc_thr.tolist()
            self.perc_val = self.perc_val.tolist()

        else:
            self.perc_thr = 0
            self.perc_val = 0

        corr_val = np.zeros((self.y_dim,))
        R2_val = np.zeros((self.y_dim,))
        for ny in range(self.y_dim):
            corr_val[ny] = np.corrcoef(Y[:, ny], Y_cv[:, ny])[0, 1]
            R2_val[ny] = 1 - np.sum(pow(Y_cv[:, ny] - Y[:, ny], 2)) / np.sum(pow(Y_cv[:, ny] - np.mean(Y_cv[:, ny]), 2))
            if np.var(Y[:, ny]) == 0:
                corr_val[ny] = 1
                R2_val[ny] = 0

        self.corr_val = corr_val
        self.R2_val = R2_val

    def save_model(self, filename):


        with open(self.work_dir + '/' + filename + '.pkl', 'wb') as file:
            pickle.dump(self.m_list, file)

        header_string_x = ' ' + ' '.join([str(elem) for elem in self.rv_name]) + ' '
        header_string_y = ' ' + ' '.join([str(elem) for elem in self.g_name])
        header_string = header_string_x + header_string_y

        xy_data = np.concatenate((np.asmatrix(np.arange(1,  self.X_hf.shape[0] + 1)).T, self.X_hf, self.Y_hf), axis=1)
        np.savetxt(self.work_dir + '/dakotaTab.out', xy_data, header=header_string, fmt='%1.4e', comments='%')
        np.savetxt(self.work_dir + '/inputTab.out', self.X_hf, header=header_string_x, fmt='%1.4e', comments='%')
        np.savetxt(self.work_dir + '/outputTab.out', self.Y_hf, header=header_string_y, fmt='%1.4e', comments='%')

        y_ub = np.zeros(self.Y_cv.shape)
        y_lb = np.zeros(self.Y_cv.shape)

        if not self.do_logtransform:
            for ny in range(self.y_dim):
                y_lb[:,ny] = norm.ppf(0.05, loc=self.Y_cv[:, ny], scale=np.sqrt(self.Y_cv_var[:, ny])).tolist()
                y_ub[:, ny] = norm.ppf(0.95, loc=self.Y_cv[:, ny],scale=np.sqrt(self.Y_cv_var[:, ny])).tolist()
        else:
            for ny in range(self.y_dim):
                mu = np.log(self.Y_cv[:, ny])
                sig = np.sqrt(np.log(self.Y_cv_var[:, ny] / pow(self.Y_cv[:, ny], 2) + 1))
                y_lb[:,ny] = lognorm.ppf(0.05, s=sig, scale=np.exp(mu)).tolist()
                y_ub[:, ny] = lognorm.ppf(0.95, s=sig, scale=np.exp(mu)).tolist()

        xy_sur_data = np.hstack((xy_data,self.Y_cv,y_lb,y_ub,self.Y_cv_var))
        g_name_sur =  self.g_name
        header_string_sur = header_string + " " + ".median ".join(
                g_name_sur) + ".median " + ".q5 ".join(g_name_sur) + ".q5 " + ".q95 ".join(
                g_name_sur) + ".q95 " + ".var ".join(g_name_sur) + ".var"

        np.savetxt(self.work_dir + '/surrogateTab.out', xy_sur_data, header=header_string_sur, fmt='%1.4e', comments='%')

        results = {}

        hfJson = {}
        hfJson["doSampling"] = self.modelInfoHF.is_model
        hfJson["doSimulation"] = self.modelInfoHF.is_model
        hfJson["DoEmethod"] = self.modelInfoHF.doe_method
        hfJson["thrNRMSE"] = self.modelInfoHF.thr_NRMSE
        hfJson["valSamp"] = self.modelInfoHF.n_existing + self.id_sim_hf
        hfJson["valSim"] = self.id_sim_hf

        results["inpData"] = self.modelInfoHF.inpData
        results["outData"] = self.modelInfoHF.outData
        results["valSamp"] = self.X_hf.shape[0]

        results["highFidelityInfo"] = hfJson

        lfJson = {}
        if self.do_mf:
            lfJson["doSampling"] = self.modelInfoLF.is_data
            lfJson["doSimulation"] = self.modelInfoLF.is_model
            lfJson["DoEmethod"] = self.modelInfoLF.doe_method
            lfJson["thrNRMSE"] = self.modelInfoLF.thr_NRMSE
            lfJson["valSamp"] = self.modelInfoLF.n_existing + self.id_sim_lf
            lfJson["valSim"] = self.id_sim_lf
            results["inpData"] = self.modelInfoLF.inpData
            results["outData"] = self.modelInfoLF.outData
            results["valSamp"] = self.X_lf.shape[0]

            results["lowFidelityInfo"] = lfJson

        else:
            results["lowFidelityInfo"] = "None"

        results["doLogtransform"] = self.do_logtransform
        results["doLinear"] = self.do_linear
        results["doMultiFidelity"] = self.do_mf
        results["kernName"] = self.kernel
        results["terminationCode"] = self.exit_code
        results["valTime"] = self.sim_time
        results["xdim"] = self.x_dim
        results["ydim"] = self.y_dim
        results["xlabels"] = self.rv_name
        results["ylabels"] = self.g_name
        results["yExact"] = {}
        results["yPredict"] = {}
        results["valNRMSE"] = {}
        results["valR2"] = {}
        results["valCorrCoeff"] = {}
        results["yPredict_CI_lb"] = {}
        results["yPredict_CI_ub"] = {}
        results["xExact"] = {}

        for nx in range(self.x_dim):
            results["xExact"][self.rv_name[nx]] = self.X_hf[:, nx].tolist()

        for ny in range(self.y_dim):
            results["yExact"][self.g_name[ny]] = self.Y_hf[:, ny].tolist()
            results["yPredict"][self.g_name[ny]] = self.Y_cv[:, ny].tolist()

            if not self.do_logtransform:
                results["yPredict_CI_lb"][self.g_name[ny]] = norm.ppf(0.25, loc = self.Y_cv[:, ny] , scale = np.sqrt(self.Y_cv_var[:, ny])).tolist()
                results["yPredict_CI_ub"][self.g_name[ny]] = norm.ppf(0.75, loc = self.Y_cv[:, ny] , scale = np.sqrt(self.Y_cv_var[:, ny])).tolist()

            else:
                mu = np.log(self.Y_cv[:, ny] )
                sig = np.sqrt(np.log(self.Y_cv_var[:, ny]/pow(self.Y_cv[:, ny] ,2)+1))
                results["yPredict_CI_lb"][self.g_name[ny]] =  lognorm.ppf(0.25, s = sig, scale = np.exp(mu)).tolist()
                results["yPredict_CI_ub"][self.g_name[ny]] =  lognorm.ppf(0.75, s = sig, scale = np.exp(mu)).tolist()

            # if self.do_logtransform:
            #         log_mean = 0
            #         log_var = float(self.m_list[ny]['Gaussian_noise.variance']) # nugget in log-space
            #         nuggetVal_linear = np.exp(2*log_mean+log_var)*(np.exp(log_var)-1) # in linear space

            if self.do_mf:
                results["valNugget1"] = {}
                results["valNugget2"] = {}
                results["valNugget1"][self.g_name[ny]] = float(self.m_list[ny].gpy_model['mixed_noise.Gaussian_noise.variance'])
                results["valNugget2"][self.g_name[ny]] = float(self.m_list[ny].gpy_model['mixed_noise.Gaussian_noise_1.variance'])
            else:
                results["valNugget"] = {}
                results["valNugget"][self.g_name[ny]] =  float(self.m_list[ny]['Gaussian_noise.variance'])
            results["valNRMSE"][self.g_name[ny]] = self.NRMSE_val[ny]
            results["valR2"][self.g_name[ny]] = self.R2_val[ny]
            results["valCorrCoeff"][self.g_name[ny]] = self.corr_val[ny]

            # if np.isnan(self.NRMSE_val[ny]):
            #     results["valNRMSE"][self.g_name[ny]] = 0
            # if np.isnan(self.R2_val[ny]):
            #     results["valR2"][self.g_name[ny]] = 0
            # if np.isnan(self.corr_val[ny]):
            #     results["valCorrCoeff"][self.g_name[ny]] = 0

        results["predError"] = {}
        results["predError"]["percent"] = self.perc_thr
        results["predError"]["value"] = self.perc_val
        results["fem"] = self.femInfo

        rv_list = []
        for nx in range(self.x_dim):
            rvs = {}
            rvs["name"] = self.rvName[nx]
            rvs["distribution"] = self.rvDist[nx]
            rvs["value"] = self.rvVal[nx]
            rv_list = rv_list + [rvs]
        results["randomVariables"] = rv_list

        ### Used for surrogate
        results["modelInfo"] = {}

        if not self.do_mf:
            for ny in range(self.y_dim):
                results["modelInfo"][self.g_name[ny]] = {}
                for parname in self.m_list[ny].parameter_names():
                    results["modelInfo"][self.g_name[ny]][parname] = list(eval('self.m_list[ny].' + parname))

        with open(self.work_dir + '/dakota.out', 'w') as fp:
            json.dump(results, fp, indent=1)

        with open(self.work_dir + '/GPresults.out', 'w') as file:

            file.write('* Problem setting\n')
            file.write('  - dimension of x : {}\n'.format(self.x_dim))
            file.write('  - dimension of y : {}\n'.format(self.y_dim))
            if self.doe_method:
                file.write("  - design of experiments : {} \n".format(self.doe_method))

            # if not self.do_doe:
            #     if self.do_simulation and self.do_sampling:
            #         file.write(
            #             "  - design of experiments (DoE) turned off - DoE evaluation time exceeds the model simulation time \n")
            file.write('\n')

            file.write('* High-fidelity model\n')
            #file.write("  - sampling : {}\n".format(self.modelInfoHF.is_model))
            file.write("  - simulation : {}\n".format(self.modelInfoHF.is_model))
            file.write('\n')

            if self.do_mf:
                file.write('* Low-fidelity model\n')
                #file.write("  - sampling : {}\n".format(self.modelInfoLF.is_model))
                file.write("  - simulation : {}\n".format(self.modelInfoLF.is_model))
                file.write('\n')

            file.write('* Convergence\n')
            file.write('  - exit code : "{}"\n'.format(self.exit_code))
            file.write('    analysis terminated ')
            if self.exit_code == 'count':
                file.write('as number of counts reached the maximum (HFmax={})\n'.format(self.modelInfoHF.thr_count))
                if self.do_mf:
                    file.write('as number of counts reached the maximum (HFmax={}, LFmax={})\n'.format(self.modelInfoHF.thr_count, self.modelInfoLF.thr_count))

            elif self.exit_code == 'accuracy':
                file.write('as minimum accuracy level (NRMSE={:.2f}) is achieved"\n'.format(self.thr_NRMSE))
            elif self.exit_code == 'time':
                file.write('as maximum running time (t={:.1f}s) reached"\n'.format(self.thr_t))
            elif self.exit_code == 'data':
                file.write('without simulation\n')
            else:
                file.write('- cannot identify the exit code\n')

            file.write('  - number of HF simulations : {}\n'.format(self.id_sim_hf))
            if self.do_mf:
                file.write('  - number of LF simulations : {}\n'.format(self.id_sim_lf))

            file.write(
                '  - maximum normalized root-mean-squared error (NRMSE): {:.5f}\n'.format(np.max(self.NRMSE_val)))

            for ny in range(self.y_dim):
                file.write('     {} : {:.2f}\n'.format(self.g_name[ny], self.NRMSE_val[ny]))

            file.write('  - analysis time : {:.1f} sec\n'.format(self.sim_time))
            file.write('  - calibration interval : {}\n'.format(self.cal_interval))
            file.write('\n')

            file.write('* GP parameters\n'.format(self.y_dim))
            file.write('  - Kernel : {}\n'.format(self.kernel))
            file.write('  - Linear : {}\n\n'.format(self.do_linear))

            if not self.do_mf:
                for ny in range(self.y_dim):
                    file.write('  [{}]\n'.format(self.g_name[ny]))
                    m_tmp = self.m_list[ny]
                    for parname in m_tmp.parameter_names():
                        file.write('    - {} '.format(parname))
                        parvals = eval('m_tmp.' + parname)
                        if len(parvals) == self.x_dim:
                            file.write('\n')
                            for nx in range(self.x_dim):
                                file.write('       {} : {:.2e}\n'.format(self.rv_name[nx], parvals[nx]))
                        else:
                            file.write(' : {:.2e}\n'.format(parvals[0]))
                    file.write('\n'.format(self.g_name[ny]))


        print("Results Saved")
        return 0

    def run_design_of_experiments(self, nc1, nq, e2, doeIdx="HF"):

        if doeIdx == "LF":
            lfset = set([tuple(x) for x in self.X_lf.tolist()])
            hfset = set([tuple(x) for x in self.X_hf.tolist()])
            hfsamples = hfset-lfset
            if len(hfsamples)==0:
                lf_additional_candi = np.zeros((0,self.x_dim))
            else:
                lf_additional_candi = np.array([np.array(x) for x in hfsamples])

            def sampling(N):
                return model_lf.sampling(N)

        else:
            def sampling(N):
                return model_hf.sampling(N)
        # doeIdx = 0
        # doeIdx = 1 #HF
        # doeIdx = 2 #LF
        # doeIdx = 3 #HF and LF

        model_hf = self.modelInfoHF
        model_lf = self.modelInfoLF

        X_hf = self.X_hf
        Y_hf = self.Y_hf
        X_lf = self.X_lf
        Y_lf = self.Y_lf
        ll = self.ll # Todo which ll?

        y_var = np.var(Y_hf, axis=0)  # normalization
        y_idx = np.argmax(np.sum(e2 / y_var, axis=0))
        if np.max(np.sum(e2 / y_var, axis=0)) == 0:
            # if this Y is constant
            self.doe_method = "none"
            self.doe_stop = True

            # dimension of interest
        m_tmp_list = self.m_list
        m_stack = copy.deepcopy(m_tmp_list[y_idx])

        r = 1

        if self.doe_method == "none":

            update_point = sampling(self.cal_interval)
            score=0

        elif self.doe_method == "pareto":

            #
            # Initial candidates
            #

            xc1 = sampling(nc1) # same for hf/lf
            xq = sampling(nq) # same for hf/lf

            if doeIdx.startswith("LF"):
                xc1 = np.vstack([xc1,lf_additional_candi])
                nc1 = xc1.shape[0]
            #
            # MMSE prediction
            #

            yc1_pred, yc1_var = self.predict(m_stack, xc1)  # use only variance
            cri1 = np.zeros(yc1_pred.shape)
            cri2 = np.zeros(yc1_pred.shape)

            for i in range(nc1):
                wei = weights_node2(xc1[i, :], X_hf, ll)
                #cri2[i] = sum(e2[:, y_idx] / Y_pred_var[:, y_idx] * wei.T)
                cri2[i] = sum(e2[:, y_idx] * wei.T)

            VOI = np.zeros(yc1_pred.shape)
            for i in range(nc1):
                pdfvals = m_stack.kern.K(np.array([xq[i]]), xq)**2/m_stack.kern.K(np.array([xq[0]]))**2
                VOI[i] = np.mean(pdfvals)*np.prod(np.diff(model_hf.xrange, axis=1)) # * np.prod(np.diff(self.xrange))
                cri1[i] = yc1_var[i] * VOI[i]

            cri1 = (cri1-np.min(cri1))/(np.max(cri1)-np.min(cri1))
            cri2 = (cri2-np.min(cri2))/(np.max(cri2)-np.min(cri2))
            logcrimi1 = np.log(cri1[:, 0])
            logcrimi2 = np.log(cri2[:, 0])

            rankid = np.zeros(nc1)
            varRank = np.zeros(nc1)
            biasRank = np.zeros(nc1)
            for id in range(nc1):
                idx_tmp = np.argwhere((logcrimi1 >= logcrimi1[id]) * (logcrimi2 >= logcrimi2[id]))
                varRank[id] = np.sum((logcrimi1 >= logcrimi1[id]))
                biasRank[id] = np.sum((logcrimi2 >= logcrimi2[id]))
                rankid[id] = idx_tmp.size

            num_1rank = np.sum(rankid==1)
            idx_1rank = list((np.argwhere(rankid==1)).flatten())

            if doeIdx.startswith("HF"):
                X_stack = X_hf
                Y_stack = Y_hf[:,y_idx][np.newaxis].T
            elif doeIdx.startswith("LF"):
                X_stack = X_lf
                Y_stack = Y_lf[:,y_idx][np.newaxis].T


            if num_1rank < self.cal_interval:
                # When number of pareto is smaller than cal_interval
                prob = np.ones((nc1,))
                prob[list(rankid==1)]=0
                prob=prob/sum(prob)
                idx_pareto = idx_1rank + list(np.random.choice(nc1, self.cal_interval-num_1rank, p=prob))
            else:
                idx_pareto_candi = idx_1rank.copy()
                m_tmp = copy.deepcopy(m_stack)

                # get MMSEw
                score = np.squeeze(cri1*cri2)
                score_candi = score[idx_pareto_candi]
                best_local = np.argsort(-score_candi)[0]
                best_global = idx_1rank[best_local]

                idx_pareto_new = [best_global]
                del idx_pareto_candi[best_local]

                for i in range(self.cal_interval-1):
                    X_stack = np.vstack([X_stack, xc1[best_global, :][np.newaxis]])
                    Y_stack = np.vstack([Y_stack, np.zeros((1, 1))]) # any variables

                    if doeIdx.startswith("HF"):
                        self.set_XY(m_stack, X_stack, Y_stack)
                    elif doeIdx.startswith("LF"):  # any variables
                        self.set_XY(m_tmp, self.X_hf, self.Y_hf, X_stack, Y_stack)

                    dummy, Yq_var = self.predict(m_stack,xc1[idx_pareto_candi, :])
                    cri1 = Yq_var * VOI[idx_pareto_candi]
                    cri1 = (cri1 - np.min(cri1)) / (np.max(cri1) - np.min(cri1))
                    score_tmp = cri1 * cri2[idx_pareto_candi] # only update the variance

                    best_local = np.argsort(-np.squeeze(score_tmp))[0]
                    best_global = idx_pareto_candi[best_local]
                    idx_pareto_new = idx_pareto_new + [best_global]
                    del idx_pareto_candi[best_local]
                idx_pareto = idx_pareto_new

            update_point = xc1[idx_pareto, :]
            score=0

        elif self.doe_method == "imse":
            update_point = np.zeros((self.cal_interval,self.x_dim))
            update_score = np.zeros((self.cal_interval,1))

            if doeIdx.startswith("HF"):
                X_stack = X_hf
                Y_stack = Y_hf[:,y_idx][np.newaxis].T
            elif doeIdx.startswith("LF"):
                X_stack = X_lf
                Y_stack = Y_lf[:,y_idx][np.newaxis].T

            for ni in range(self.cal_interval):
                #
                # Initial candidates
                #
                xc1 = sampling(nc1) # same for hf/lf
                if doeIdx.startswith("LF"):
                    xc1 = np.vstack([xc1, lf_additional_candi])
                    nc1 = xc1.shape[0]

                xq = sampling(nq) # same for hf/lf


                dummy, Yq_var = self.predict(m_stack, xq)
                if ni==0:
                    IMSEbase = 1 / xq.shape[0] * sum(Yq_var.flatten())

                tmp = time.time()
                if self.do_parallel:
                    iterables = ((copy.deepcopy(m_stack), xc1[i, :][np.newaxis], xq, np.ones((nq, self.y_dim)), i, y_idx, doeIdx) for i in range(nc1))
                    result_objs = list(self.pool.starmap(imse, iterables))
                    IMSEc1 = np.zeros(nc1)
                    for IMSE_val, idx in result_objs:
                        IMSEc1[idx] = IMSE_val
                    print("IMSE: finding the next DOE {} - parallel .. time = {:.2f}".format(ni, time.time() - tmp))  # 7s # 3-4s
                    # TODO: terminate it gracefully....
                    # see https://stackoverflow.com/questions/21104997/keyboard-interrupt-with-pythons-multiprocessing
                    try:
                        while True:
                            time.sleep(0.5)
                            if all([r.ready() for r in result]):
                                break
                    except KeyboardInterrupt:
                        pool.terminate()
                        pool.join()

                else:
                    IMSEc1 = np.zeros(nc1)
                    for i in range(nc1):
                        IMSEc1[i], dummy = imse(copy.deepcopy(m_stack), xc1[i, :][np.newaxis], xq, np.ones((nq, self.y_dim)), i, y_idx, doeIdx)
                    print("IMSE: finding the next DOE {} - serial .. time = {}".format(ni, time.time() - tmp))  # 4s

                new_idx = np.argmin(IMSEc1, axis=0)
                x_point = xc1[new_idx, :][np.newaxis]

                X_stack = np.vstack([X_stack, x_point])
                Y_stack = np.vstack([Y_stack, np.zeros((1, 1))])  # any variables
                update_point[ni, :] = x_point

                if doeIdx=="HFHF":
                    self.set_XY(m_stack, X_stack, Y_stack, self.X_lf, self.Y_lf[:,y_idx][np.newaxis].T)
                elif doeIdx == "HF":
                    self.set_XY(m_stack, X_stack, Y_stack)
                elif doeIdx=="LF":  # any variables
                    self.set_XY(m_stack, self.X_hf, self.Y_hf[:,y_idx][np.newaxis].T, X_stack, Y_stack)

            score=IMSEbase-np.min(IMSEc1, axis=0)

        elif self.doe_method == "imsew":
            update_point = np.zeros((self.cal_interval,self.x_dim))
            update_score = np.zeros((self.cal_interval,1))


            if doeIdx.startswith("HF"):
                X_stack = X_hf
                Y_stack = Y_hf[:,y_idx][np.newaxis].T
            elif doeIdx.startswith("LF"):
                X_stack = X_lf
                Y_stack = Y_lf[:,y_idx][np.newaxis].T


            for ni in range(self.cal_interval):
                #
                # Initial candidates
                #
                xc1 = sampling(nc1) # same for hf/lf
                if doeIdx.startswith("LF"):
                    xc1 = np.vstack([xc1, lf_additional_candi])
                    nc1 = xc1.shape[0]

                xq = sampling(nq) # same for hf/lf

                phiq = np.zeros((nq, self.y_dim))
                for i in range(nq):
                    phiq[i,:] = e2[closest_node(xq[i, :], X_hf, ll)]
                phiqr = pow(phiq[:, y_idx], r)

                dummy, Yq_var = self.predict(m_stack, xq)
                if ni==0:
                    IMSEbase = 1 / xq.shape[0] * sum(phiqr.flatten() * Yq_var.flatten())

                tmp = time.time()
                if self.do_parallel:
                    iterables = ((copy.deepcopy(m_stack), xc1[i, :][np.newaxis], xq, phiqr, i, y_idx, doeIdx) for i in range(nc1))
                    result_objs = list(self.pool.starmap(imse, iterables))
                    IMSEc1 = np.zeros(nc1)
                    for IMSE_val, idx in result_objs:
                        IMSEc1[idx] = IMSE_val
                    print("IMSE: finding the next DOE {} - parallel .. time = {:.2f}".format(ni, time.time() - tmp))  # 7s # 3-4s
                else:
                    IMSEc1 = np.zeros(nc1)
                    for i in range(nc1):
                        IMSEc1[i], dummy = imse(copy.deepcopy(m_stack), xc1[i, :][np.newaxis], xq, phiqr, i, y_idx, doeIdx)
                        if np.mod(i,200)==0:
                            print("IMSE iter {}, candi {}/{}".format(ni, i, nc1))  # 4s
                    print("IMSE: finding the next DOE {} - serial .. time = {}".format(ni, time.time() - tmp))  # 4s

                new_idx = np.argmin(IMSEc1, axis=0)
                x_point = xc1[new_idx, :][np.newaxis]

                X_stack = np.vstack([X_stack, x_point])
                Y_stack = np.vstack([Y_stack, np.zeros((1, 1))])  # any variables
                update_point[ni, :] = x_point


                if doeIdx=="HFHF":
                    self.set_XY(m_stack, X_stack, Y_stack, self.X_lf, self.Y_lf[:,y_idx][np.newaxis].T)
                elif doeIdx == "HF":
                    self.set_XY(m_stack, X_stack, Y_stack)
                elif doeIdx=="LF":  # any variables
                    self.set_XY(m_stack, self.X_hf, self.Y_hf[:,y_idx][np.newaxis].T, X_stack, Y_stack)


            score=IMSEbase-np.min(IMSEc1, axis=0)


        elif self.doe_method == "mmsew":
            if doeIdx.startswith("HF"):
                X_stack = X_hf
                Y_stack = Y_hf[:,y_idx][np.newaxis].T
            elif doeIdx.startswith("LF"):
                X_stack = X_lf
                Y_stack = Y_lf[:,y_idx][np.newaxis].T

            update_point = np.zeros((self.cal_interval,self.x_dim))

            for ni in range(self.cal_interval):

                xc1 = sampling(nc1)  # same for hf/lf
                if doeIdx.startswith("LF"):
                    xc1 = np.vstack([xc1, lf_additional_candi])
                    nc1 = xc1.shape[0]

                phic = np.zeros((nc1, self.y_dim))
                for i in range(nc1):
                    phic[i, :] = e2[closest_node(xc1[i, :], X_hf, ll)]
                phicr = pow(phic[:, y_idx], r)

                yc1_pred, yc1_var = self.predict(m_stack,xc1)  # use only variance
                MMSEc1 = yc1_var.flatten() * phicr.flatten()
                new_idx = np.argmax(MMSEc1, axis=0)
                x_point = xc1[new_idx, :][np.newaxis]

                X_stack = np.vstack([X_stack, x_point])
                Y_stack = np.vstack([Y_stack,  np.zeros((1, 1))])  # any variables
                #m_stack.set_XY(X=X_stack, Y=Y_stack)
                if doeIdx.startswith("HF"):
                    self.set_XY(m_stack, X_stack, Y_stack)
                elif doeIdx.startswith("LF"):  # any variables
                    self.set_XY(m_tmp, self.X_hf, self.Y_hf, X_stack, Y_stack)
                update_point[ni, :] = x_point

            score = np.max(MMSEc1, axis=0)
            
        elif self.doe_method == "mmse":

            if doeIdx.startswith("HF"):
                X_stack = X_hf
                Y_stack = Y_hf[:,y_idx][np.newaxis].T
            elif doeIdx.startswith("LF"):
                X_stack = X_lf
                Y_stack = Y_lf[:,y_idx][np.newaxis].T


            update_point = np.zeros((self.cal_interval,self.x_dim))

            for ni in range(self.cal_interval):

                xc1 = sampling(nc1)  # same for hf/lf
                if doeIdx.startswith("LF"):
                    xc1 = np.vstack([xc1, lf_additional_candi])
                    nc1 = xc1.shape[0]

                yc1_pred, yc1_var = self.predict(m_stack,xc1)  # use only variance
                MMSEc1 = yc1_var.flatten()
                new_idx = np.argmax(MMSEc1, axis=0)
                x_point = xc1[new_idx, :][np.newaxis]

                X_stack = np.vstack([X_stack, x_point])
                Y_stack = np.vstack([Y_stack,  np.zeros((1, 1))])  # any variables
                #m_stack.set_XY(X=X_stack, Y=Y_stack)

                # if doeIdx.startswith("HF"):
                #     self.set_XY(m_stack, X_stack, Y_stack)
                # elif doeIdx.startswith("LF"):  # any variables
                #     self.set_XY(m_stack, self.X_hf, self.Y_hf, X_stack, Y_stack)

                if doeIdx=="HFHF":
                    self.set_XY(m_stack, X_stack, Y_stack, self.X_lf, self.Y_lf[:,y_idx][np.newaxis].T)
                elif doeIdx == "HF":
                    self.set_XY(m_stack, X_stack, Y_stack)
                elif doeIdx=="LF":  # any variables
                    self.set_XY(m_stack, self.X_hf, self.Y_hf[:,y_idx][np.newaxis].T, X_stack, Y_stack)

                update_point[ni, :] = x_point

            score = np.max(MMSEc1, axis=0)
        else:
            msg = 'Error running SimCenterUQ: cannot identify the doe method <' + self.doe_method + '>'
            self.exit(msg)

        return update_point, y_idx, score

    def normalized_mean_sq_error(self, yp, ye):
        n = yp.shape[0]
        data_bound = (np.max(ye, axis=0) - np.min(ye, axis=0))
        RMSE = np.sqrt(1 / n * np.sum(pow(yp - ye, 2), axis=0))
        NRMSE = RMSE/data_bound
        NRMSE[np.argwhere((data_bound ==0))]=0
        return NRMSE

    def get_cross_validation_err(self):

        X_hf = self.X_hf
        Y_hf = self.Y_hf
        X_lf = self.X_lf
        Y_lf = self.Y_lf


        e2 = np.zeros(Y_hf.shape)
        Y_pred = np.zeros(Y_hf.shape)
        Y_pred_var = np.zeros(Y_hf.shape)
        for ny in range(Y_hf.shape[1]):
            m_tmp = copy.deepcopy( self.m_list[ny])
            for ns in range(X_hf.shape[0]):
                X_tmp = np.delete(X_hf, ns, axis=0)
                Y_tmp = np.delete(Y_hf, ns, axis=0)
                m_tmp = self.set_XY(m_tmp, X_tmp,Y_tmp[:, ny][np.newaxis].transpose(), X_lf, Y_lf[:, ny][np.newaxis].transpose())
                x_loo = X_hf[ns, :][np.newaxis]
                Y_pred_tmp, Y_err_tmp = self.predict(m_tmp,x_loo)

                Y_pred[ns, ny] = Y_pred_tmp
                Y_pred_var[ns, ny] = Y_err_tmp

                if self.do_logtransform:
                    Y_exact =  np.log(Y_hf[ns, ny])
                else:
                    Y_exact =  Y_hf[ns, ny]


                e2[ns, ny] = pow((Y_pred_tmp - Y_exact), 2)  # for nD outputs

        return Y_pred, Y_pred_var, e2

def imse(m_tmp, xcandi, xq, phiqr, i,y_idx, doeIdx="HF"):
    if doeIdx == "HF":
        X = m_tmp.X
        Y = m_tmp.Y
        X_tmp = np.vstack([X, xcandi])
        Y_tmp = np.vstack([Y, np.zeros((1, Y.shape[1]))])   # any variables
        #self.set_XY(m_tmp, X_tmp, Y_tmp)
        m_tmp.set_XY(X_tmp, Y_tmp)
        dummy, Yq_var = m_tmp.predict(xq)
    
    elif doeIdx == "HFHF":
        idxHF = np.argwhere(m_tmp.gpy_model.X[:, -1] == 0).T[0]
        idxLF = np.argwhere(m_tmp.gpy_model.X[:, -1] == 1).T[0]
        X_hf = m_tmp.gpy_model.X[idxHF, :-1]
        Y_hf = m_tmp.gpy_model.Y[idxHF, :]
        X_lf = m_tmp.gpy_model.X[idxLF, :-1]
        Y_lf = m_tmp.gpy_model.Y[idxLF, :]
        X_tmp = np.vstack([X_hf, xcandi])
        Y_tmp = np.vstack([Y_hf, np.zeros((1, Y_hf.shape[1]))])  # any variables
        #self.set_XY(m_tmp, X_tmp, Y_tmp, X_lf, Y_lf)
        X_list_tmp, Y_list_tmp = emf.convert_lists_to_array.convert_xy_lists_to_arrays([X_tmp, X_lf], [Y_tmp, Y_lf])
        m_tmp.set_data(X=X_list_tmp, Y=Y_list_tmp)
        xq_list = convert_x_list_to_array([xq, np.zeros((0,xq.shape[1]))])
        dummy, Yq_var = m_tmp.predict(xq_list)
        
    elif doeIdx.startswith("LF"):
        idxHF = np.argwhere(m_tmp.gpy_model.X[:,-1]==0).T[0]
        idxLF = np.argwhere(m_tmp.gpy_model.X[:,-1]==1).T[0]
        X_hf = m_tmp.gpy_model.X[idxHF, :-1]
        Y_hf = m_tmp.gpy_model.Y[idxHF, :]
        X_lf = m_tmp.gpy_model.X[idxLF, :-1]
        Y_lf = m_tmp.gpy_model.Y[idxLF, :]
        X_tmp = np.vstack([X_lf, xcandi])
        Y_tmp = np.vstack([Y_lf, np.zeros((1, Y_lf.shape[1]))])      # any variables
        #self.set_XY(m_tmp, X_hf, Y_hf, X_tmp, Y_tmp)
        X_list_tmp, Y_list_tmp = emf.convert_lists_to_array.convert_xy_lists_to_arrays([X_hf, X_tmp], [Y_hf, Y_tmp])
        m_tmp.set_data(X=X_list_tmp, Y=Y_list_tmp)
        xq_list = convert_x_list_to_array([xq, np.zeros((0,xq.shape[1]))])
        dummy, Yq_var = m_tmp.predict(xq_list)
    else:
        print("doe method <{}> is not supported".format(doeIdx))

    #dummy, Yq_var = self.predict(m_tmp,xq)
    IMSEc1 = 1 / xq.shape[0] * sum(phiqr.flatten() * Yq_var.flatten())

    return IMSEc1, i


class model_info:
    def __init__(self, surrogateJson, rvJson, work_dir, x_dim, y_dim, errfile, n_processor, idx=0):

        def exit_tmp(msg):
            print(msg)
            errfile.write(msg)
            errfile.close()
            exit(-1)
        # idx = -1 : no info (dummy) paired with 0
        # idx = 0 : single fidelity
        # idx = 1 : high fidelity FEM run with tag 1
        # idx = 2 : low fidelity
        self.idx = idx
        self.x_dim = x_dim
        self.y_dim = y_dim
        #
        # Get [X_existing, Y_existing, n_existing, n_total]
        #

        self.model_without_sampling = False # default
        if idx==0:
            # not MF
            if surrogateJson["method"] == "Sampling and Simulation":
                self.is_model = True
                self.is_data = surrogateJson["existingDoE"]
            elif surrogateJson["method"] == "Import Data File":
                self.is_model = False
                self.is_data = True
                if surrogateJson["outputData"]:
                    self.model_without_sampling = True
            else:
                msg = 'Error reading json: either select "Import Data File" or "Sampling and Simulation"'
                exit_tmp(msg)

        elif idx==1 or idx==2:
            # MF
            self.is_data = True  # default
            self.is_model = surrogateJson["fromModel"]
            if self.is_model:
                self.is_data = surrogateJson["existingDoE"]

        elif idx==-1:
            self.is_data = False
            self.is_model = False

        if idx==0:
            # single model
            input_file = "templatedir/inpFile.in"
            output_file = "templatedir/outFile.in"
        elif idx==1:
            # high-fidelity
            input_file = "templatedir/inpFile_HF.in"
            output_file = "templatedir/outFile_HF.in"
        elif idx==2:
            # low-fidelity
            input_file = "templatedir/inpFile_LF.in"
            output_file = "templatedir/outFile_LF.in"

        if self.is_data:
            self.inpData = os.path.join(work_dir, input_file)
            self.outData = os.path.join(work_dir, output_file)

            def exit_func(msg):
                self.exit(msg)

            self.X_existing = read_txt(self.inpData, exit_func)
            if not self.model_without_sampling:
                self.Y_existing = read_txt(self.outData, exit_func)
            self.n_existing = self.X_existing.shape[0]

            if not (self.X_existing.shape[1] == self.x_dim):
                msg = 'Error importing input data - dimension inconsistent: have {} RV(s) but have {} column(s).'.format(
                    self.x_dim, self.X_existing.shape[1])
                exit_tmp(msg)

            if not (self.Y_existing.shape[1] == self.y_dim):
                msg = 'Error importing input data - dimension inconsistent: have {} QoI(s) but have {} column(s).'.format(
                    self.y_dim, self.Y_existing.shape[1])
                exit_tmp(msg)

            if (not (self.Y_existing.shape[0] == self.X_existing.shape[0])) and (not self.model_without_sampling):
                msg = 'Error importing input data: numbers of samples of inputs ({}) and outputs ({}) are inconsistent'.format(
                    self.X_existing.shape[0], self.Y_existing.shape[0])
                exit_tmp(msg)

        else:
            self.inpData = ""
            self.outData = ""
            self.X_existing = np.zeros((0,x_dim))
            self.Y_existing = np.zeros((0,y_dim))
            self.n_existing = 0

        if self.is_model:
            self.doe_method = surrogateJson["DoEmethod"]
            self.thr_count = surrogateJson['samples']  # number of samples
            if self.doe_method == "None":
                self.user_init = self.thr_count
            else:
                try:
                    self.user_init = surrogateJson["initialDoE"]
                except:
                    self.user_init = -1 #automate
            ## convergence criteria
            self.thr_NRMSE = surrogateJson["accuracyLimit"]
            self.thr_t = surrogateJson["timeLimit"] * 60

            self.xrange = np.empty((0, 2), float)
            for rv in rvJson:
                if "lowerbound" not in rv:
                    msg = 'Error in input RV: all RV should be set to Uniform distribution'
                    exit_tmp(msg)
                self.xrange = np.vstack((self.xrange, [rv['lowerbound'], rv['upperbound']]))

        else:
            self.doe_method = "None"
            self.user_init = 0
            self.thr_count = 0
            self.thr_NRMSE = 0
            self.thr_t = float('inf')
            if self.is_data:
                self.xrange = np.vstack([np.min(self.X_existing, axis=0), np.max(self.X_existing, axis=0)]).T
            else:
                self.xrange = np.zeros((self.x_dim,2))
        #TODO should I use "effective" number of dims?
        self.ll = self.xrange[:, 1] - self.xrange[:, 0]
        if self.user_init <0: # automated choice 8*D
            n_init_tmp = int(np.ceil(8*self.x_dim/n_processor)*n_processor)
        else:
            n_init_tmp = int(np.ceil(self.user_init/n_processor)*n_processor) # Make every workers busy
        self.n_init = min(self.thr_count,n_init_tmp)
        #self.n_init = 4
        self.doe_method = self.doe_method.lower()

    def sampling(self,n):
        if n>0:
            X_tmp = np.zeros((n, self.x_dim))
            U = lhs(self.x_dim, samples=n)
            for nx in range(self.x_dim):
                X_tmp[:, nx] = U[:, nx] * (self.xrange[nx, 1] - self.xrange[nx, 0]) + self.xrange[nx, 0]
        else:
            X_tmp=np.zeros((0,self.x_dim))
        return X_tmp

    # def set_FEM(self, rv_name, do_parallel, y_dim, t_init):
    #     self.rv_name = rv_name
    #     self.do_parallel = do_parallel
    #     self.y_dim = y_dim
    #     self.t_init = t_init
    #     self.total_sim_time = 0
    #
    # def run_FEM(self,X, id_sim):
    #     tmp = time.time()
    #     if self.is_model:
    #         X, Y, id_sim = self.run_FEM_batch(X, id_sim, self.rv_name, self.do_parallel, self.y_dim, self.t_init, self.thr_t, runIdx=self.runIdx)
    #
    #     else:
    #         X, Y, id_sim =  np.zeros((0, self.x_dim)), np.zeros((0, self.y_dim)), id_sim
    #
    #     self.total_sim_time += tmp
    #     self.avg_sim_time = self.total_sim_time / id_sim
    #
    #     return X, Y, id_sim

### Additional functions

def weights_node2(node, nodes, ls):
    nodes = np.asarray(nodes)
    deltas = nodes - node
    deltas_norm = np.zeros(deltas.shape)
    for nx in range(ls.shape[0]):
        deltas_norm[:, nx] = (deltas[:, nx]) / ls[nx]  * nodes.shape[0]# additional weights?
    dist_ls = np.sqrt(np.sum(pow(deltas_norm, 2), axis=1))
    weig = np.exp(-pow(dist_ls,2))
    if (sum(weig)==0):
        weig = np.ones(nodes.shape[0])
    return weig/sum(weig)

def closest_node(x, X, ll):

    X = np.asarray(X)
    deltas = X - x
    deltas_norm = np.zeros(deltas.shape)
    for nx in range(X.shape[1]):
        deltas_norm[:, nx] = deltas[:, nx] /  ll[nx]
    dist_2 = np.einsum('ij,ij->i', deltas_norm, deltas_norm) # square sum

    return np.argmin(dist_2)


def read_txt(text_dir,exit_fun):
    if not os.path.exists(text_dir):
        msg = "Error: file does not exist: " + text_dir
        exit_fun(msg)
    with open(text_dir) as f:
        # Iterate through the file until the table starts
        header_count = 0
        for line in f:
            if line.startswith('%'):
                header_count = header_count + 1
                #print(line)
        try:
            with open(text_dir) as f:
                X = np.loadtxt(f, skiprows=header_count)
        except ValueError:
            with open(text_dir) as f:
                try:
                    X = np.genfromtxt(f, skip_header=header_count, delimiter=',')
                    # if there are extra delimiter, remove nan
                    if np.isnan(X[-1, -1]):
                        X = np.delete(X, -1, 1)
                    # X = np.loadtxt(f, skiprows=header_count, delimiter=',')
                except ValueError:
                    msg = "Error: file format is not supported " + text_dir
                    exit_fun(msg)
    if X.ndim == 1:
        X = np.array([X]).transpose()

    return X

if __name__ == "__main__":
    main(sys.argv)
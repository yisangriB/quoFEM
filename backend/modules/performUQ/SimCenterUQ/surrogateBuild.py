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
import random

from multiprocessing import Pool

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
    error_tag=False
except:
    error_tag=True


class GpFromModel(object):

    def __init__(self, work_dir, run_type, os_type, inp, errlog):

        t_init = time.time()
        self.errlog = errlog
        self.work_dir = work_dir
        self.os_type = os_type
        self.run_type = run_type

        #
        # From external READ JSON FILE
        #

        rv_name = list()
        self.g_name = list()
        x_dim = 0
        y_dim = 0

        for rv in inp['randomVariables']:
            rv_name = rv_name + [rv['name']]
            x_dim += 1

        if x_dim == 0:
            msg = 'Error reading json: RV is empty'
            errlog.exit(msg)

        for g in inp['EDP']:
            if g['length']==1: # scalar
                self.g_name = self.g_name + [g['name']]
                y_dim += 1
            else: # vector
                for nl in range(g['length']):
                    self.g_name = self.g_name + ["{}_{}".format(g['name'],nl+1)]
                    y_dim += 1

        if y_dim == 0:
            msg = 'Error reading json: EDP(QoI) is empty'
            errlog.exit(msg)

        # Accuracy is also sensitive to the range of X
        self.id_sim = 0
        self.x_dim = x_dim
        self.y_dim = y_dim
        self.rv_name = rv_name

        self.do_predictive = False
        automate_doe = False

        surrogateInfo = inp["UQ_Method"]["surrogateMethodInfo"]

        try:
            self.do_parallel = surrogateInfo["parallelExecution"]
        except:
            self.do_parallel = True

        if self.do_parallel:
            if self.run_type.lower() == 'runninglocal':
                self.n_processor = os.cpu_count()
                from multiprocessing import Pool
                self.pool = Pool(self.n_processor)
            else:
                # Always
                from mpi4py import MPI
                from mpi4py.futures import MPIPoolExecutor
                self.world = MPI.COMM_WORLD
                self.pool = MPIPoolExecutor()
                self.n_processor = self.world.Get_size()
                #self.n_processor =20
            print("nprocessor :")
            print(self.n_processor)
            #self.cal_interval = 5
            self.cal_interval = self.n_processor

        else:
            self.pool = 0
            self.cal_interval = 5

        if surrogateInfo["method"] == "Sampling and Simulation":
            self.do_mf = False
            do_sampling = True
            do_simulation = True
            self.use_existing = surrogateInfo["existingDoE"]
            if self.use_existing:
                self.inpData = os.path.join(work_dir, "templatedir/inpFile.in")
                self.outData = os.path.join(work_dir, "templatedir/outFile.in")
            thr_count = surrogateInfo['samples']  # number of samples


            if surrogateInfo["advancedOpt"]:
                self.doe_method = surrogateInfo["DoEmethod"]
                if surrogateInfo["DoEmethod"] == "None":
                    do_doe = False
                    user_init = thr_count
                else:
                    do_doe = True
                    user_init = surrogateInfo["initialDoE"]
            else:
                self.doe_method = "pareto" #default
                do_doe = True
                user_init = -100

        elif surrogateInfo["method"] == "Import Data File":
            self.do_mf = False
            do_sampling = False
            do_simulation = not surrogateInfo["outputData"]
            self.doe_method = "None"  # default
            do_doe = False
            # self.inpData = surrogateInfo['inpFile']
            self.inpData = os.path.join(work_dir, "templatedir/inpFile.in")
            if not do_simulation:
                # self.outData = surrogateInfo['outFile']
                self.outData = os.path.join(work_dir, "templatedir/outFile.in")

        elif surrogateInfo["method"] == "Import Multi-fidelity Data File":
            self.do_mf = True
            self.doe_method = "None"  # default

            self.hf_is_model = surrogateInfo['HFfromModel']
            self.lf_is_model = surrogateInfo['LFfromModel']

            if self. hf_is_model:
                self.use_existing_hf = surrogateInfo["existingDoE_HF"]
                self.samples_hf = surrogateInfo["samples_HF"]
                if self.use_existing_hf:
                    self.inpData = os.path.join(work_dir, "templatedir/inpFile_HF.in")
                    self.outData = os.path.join(work_dir, "templatedir/outFile_HF.in")
            else:
                self.inpData_hf = os.path.join(work_dir, "templatedir/inpFile_HF.in")
                self.outData_hf = os.path.join(work_dir, "templatedir/outFile_HF.in")
                self.X_hf = read_txt(self.inpData_hf, errlog)
                self.Y_hf = read_txt(self.outData_hf, errlog)
                if self.X_hf.shape[0] != self.Y_hf.shape[0]:
                    msg = 'Error reading json: high fidelity input and output files should have the same number of rows'
                    errlog.exit(msg)

            if self.lf_is_model:
                self.use_existing_lf = surrogateInfo["existingDoE_LF"]
                self.samples_lf = surrogateInfo["samples_LF"]
                if self.use_existing_lf:
                    self.inpData = os.path.join(work_dir, "templatedir/inpFile_LF.in")
                    self.outData = os.path.join(work_dir, "templatedir/outFile_LF.in")
            else:
                self.inpData_lf = os.path.join(work_dir, "templatedir/inpFile_LF.in")
                self.outData_lf = os.path.join(work_dir, "templatedir/outFile_LF.in")
                self.X_lf = read_txt(self.inpData_lf, errlog)
                self.Y_lf = read_txt(self.outData_lf, errlog)
                if self.X_lf.shape[0] != self.Y_lf.shape[0]:
                    msg = 'Error reading json: low fidelity input and output files should have the same number of rows'
                    errlog.exit(msg)

            if (not self.hf_is_model) and self.lf_is_model:
                self.mf_case = "data-model"
                do_sampling = True
                do_simulation = True
                do_doe = surrogateInfo["doDoE"]
                self.use_existing = self.use_existing_lf
                if self.lf_is_model:
                    if self.use_existing_lf:
                        self.inpData = self.inpData_lf
                        self.oupData = self.outData_lf
                else:
                    self.inpData = self.inpData_lf
                    self.outData = self.outData_lf
                if do_doe:
                    user_init = -100
                else:
                    user_init = self.samples_lf
                thr_count = self.samples_lf  # number of samples

            elif self.hf_is_model and (not self.lf_is_model):
                self.mf_case = "model-data"
                do_sampling = True
                do_simulation = True
                do_doe = surrogateInfo["doDoE"]
                self.use_existing = self.use_existing_hf
                if self.hf_is_model:
                    if self.use_existing_hf:
                        self.inpData = self.inpData_hf
                        self.oupData = self.outData_hf
                else:
                    self.inpData = self.inpData_hf
                    self.outData = self.outData_hf
                if do_doe:
                    user_init = -100
                else:
                    user_init = self.samples_hf
                thr_count = self.samples_hf  # number of samples

            elif self.hf_is_model and self.lf_is_model:
                self.mf_case = "model-model"
                do_sampling = True
                do_simulation = True
                do_doe = surrogateInfo["doDoE"]
                self.use_existing = self.use_existing_hf
                if do_doe:
                    user_init = -100
                    user_init_lf = -100
                else:
                    user_init = self.samples_hf
                    user_init_lf = self.samples_lf
                thr_count = self.samples_hf  # number of samples
                thr_count_lf = self.samples_lf  # number of samples

            elif (not self.hf_is_model) and (not self.lf_is_model):
                self.mf_case = "data-data"
                do_sampling = False
                do_simulation = False
                do_doe = False
                self.inpData = self.inpData_lf
                self.outData = self.outData_lf

        else:
            msg = 'Error reading json: either select "Import Data File" or "Sampling and Simulation"'
            errlog.exit(msg)

        if surrogateInfo["advancedOpt"]:
            self.do_logtransform = surrogateInfo["logTransform"]
            kernel = surrogateInfo["kernel"]
            do_linear = surrogateInfo["linear"]
            nugget_opt = surrogateInfo["nuggetOpt"]
            try:
                self.nuggetVal = np.array(json.loads("[{}]".format(surrogateInfo["nuggetString"])))
            except json.decoder.JSONDecodeError:
                msg = 'Error reading json: improper format of nugget values/bounds. Provide nugget values/bounds of each QoI with comma delimiter'
                errlog.exit(msg)

            if self.nuggetVal.shape[0]!=self.y_dim and self.nuggetVal.shape[0]!=0 :
                msg = 'Error reading json: Number of nugget quantities ({}) does not match # QoIs ({})'.format(self.nuggetVal.shape[0],self.y_dim)
                errlog.exit(msg)

            if nugget_opt == "Fixed Values":
                for Vals in self.nuggetVal:
                    if (not np.isscalar(Vals)):
                        msg = 'Error reading json: provide nugget values of each QoI with comma delimiter'
                        errlog.exit(msg)
            elif nugget_opt == "Fixed Bounds":
                for Bous in self.nuggetVal:
                    if (np.isscalar(Bous)):
                        msg = 'Error reading json: provide nugget bounds of each QoI in brackets with comma delimiter, e.g. [0.0,1.0],[0.0,2.0],...'
                        errlog.exit(msg)
                    elif (isinstance(Bous,list)):
                        msg = 'Error reading json: provide both lower and upper bounds of nugget'
                        errlog.exit(msg)
                    elif Bous.shape[0]!=2:
                        msg = 'Error reading json: provide nugget bounds of each QoI in brackets with comma delimiter, e.g. [0.0,1.0],[0.0,2.0],...'
                        errlog.exit(msg)
                    elif Bous[0]>Bous[1]:
                        msg = 'Error reading json: the lower bound of a nugget value should be smaller than its upper bound'
                        errlog.exit(msg)

            # if self.do_logtransform:
            #     mu = 0
            #     sig2 = self.nuggetVal

            #     #median = np.exp(mu)
            #     #mean = np.exp(mu + sig2/2)
            #     self.nuggetVal = np.exp(2*mu + sig2)*(np.exp(sig2)-1)

        else:
            self.do_logtransform = False
            kernel = 'Matern 5/2'
            do_linear = False
            #do_nugget = True
            nugget_opt = "optimize"

        if do_simulation:
            if not self.do_mf:
                femInfo = inp["fem"]
                self.inpFile = femInfo["inputFile"]
                self.postFile = femInfo["postprocessScript"]
                self.appName = femInfo["program"]

        #
        # get x points
        #

        if do_sampling:
            thr_NRMSE = surrogateInfo["accuracyLimit"]
            thr_t = surrogateInfo["timeLimit"] * 60

            np.random.seed(surrogateInfo['seed'])
            random.seed(surrogateInfo['seed'])
            self.xrange = np.empty((0, 2), float)
            for rv in inp['randomVariables']:
                if  "lowerbound" not in rv:
                    msg = 'Error in input RV: all RV should be set to Uniform distribution'
                    errlog.exit(msg)
                self.xrange = np.vstack((self.xrange, [rv['lowerbound'], rv['upperbound']]))
            self.len = np.abs(np.diff(self.xrange).T[0])

            if sum(self.len == 0) > 0:
                msg = 'Error in input RV: training range of RV should be greater than 0'
                errlog.exit(msg)

            #
            # Read existing samples
            #

            if not self.do_mf:
                if self.use_existing:
                    X_tmp = read_txt(self.inpData,errlog)
                    Y_tmp = read_txt(self.outData,errlog)
                    n_ex = X_tmp.shape[0]

                    if self.do_mf:
                        if X_tmp.shape[1] != self.X_hf.shape[1]:
                            msg = 'Error importing input data: dimension inconsistent: high fidelity data have {} RV column(s) but low fidelity model have {}.'.format(
                                self.X_hf.shape[1], X_tmp.shape[1])
                            errlog.exit(msg)

                        if Y_tmp.shape[1] != self.Y_hf.shape[1]:
                            msg = 'Error importing input data: dimension inconsistent: high fidelity data have {} QoI column(s) but low fidelity model have {}.'.format(
                                self.Y_hf.shape[1], Y_tmp.shape[1])
                            errlog.exit(msg)

                    if X_tmp.shape[1] != x_dim:
                        msg = 'Error importing input data: dimension inconsistent: have {} RV(s) but have {} column(s).'.format(
                            x_dim, X_tmp.shape[1])
                        errlog.exit(msg)

                    if Y_tmp.shape[1] != y_dim:
                        msg = 'Error importing input data: dimension inconsistent: have {} QoI(s) but have {} column(s).'.format(
                            y_dim, Y_tmp.shape[1])
                        errlog.exit(msg)

                    if n_ex != Y_tmp.shape[0]:
                        msg = 'Error importing input data: numbers of samples of inputs ({}) and outputs ({}) are inconsistent'.format(n_ex, Y_tmp.shape[0])
                        errlog.exit(msg)
                else:
                    n_ex = 0
                    if user_init ==0:
                        #msg = 'Error reading json: # of initial DoE should be greater than 0'
                        #errlog.exit(msg)
                        user_init = -1;
                    X_tmp = np.zeros((0, x_dim))
                    Y_tmp = np.zeros((0, y_dim))

                if user_init < 0:
                    n_init_ref = min(4 * x_dim, thr_count + n_ex - 1, 500)
                    if self.do_parallel:
                        n_init_ref = int(
                            np.ceil(n_init_ref / self.n_processor) * self.n_processor)  # Let's not waste resource
                    if n_init_ref > n_ex:
                        n_init = n_init_ref - n_ex
                    else:
                        n_init = 0
                else:
                    n_init = user_init


            if self.do_mf:
                if self.hf_is_model:
                    if self.use_existing_hf:
                        X_tmp = read_txt(self.inpData,errlog)
                        Y_tmp = read_txt(self.outData,errlog)
                        n_ex = X_tmp.shape[0]

                        if self.do_mf:
                            if X_tmp.shape[1] != self.X_hf.shape[1]:
                                msg = 'Error importing input data: dimension inconsistent: high fidelity data have {} RV column(s) but low fidelity model have {}.'.format(
                                    self.X_hf.shape[1], X_tmp.shape[1])
                                errlog.exit(msg)

                            if Y_tmp.shape[1] != self.Y_hf.shape[1]:
                                msg = 'Error importing input data: dimension inconsistent: high fidelity data have {} QoI column(s) but low fidelity model have {}.'.format(
                                    self.Y_hf.shape[1], Y_tmp.shape[1])
                                errlog.exit(msg)

                        if X_tmp.shape[1] != x_dim:
                            msg = 'Error importing input data: dimension inconsistent: have {} RV(s) but have {} column(s).'.format(
                                x_dim, X_tmp.shape[1])
                            errlog.exit(msg)

                        if Y_tmp.shape[1] != y_dim:
                            msg = 'Error importing input data: dimension inconsistent: have {} QoI(s) but have {} column(s).'.format(
                                y_dim, Y_tmp.shape[1])
                            errlog.exit(msg)

                        if n_ex != Y_tmp.shape[0]:
                            msg = 'Error importing input data: numbers of samples of inputs ({}) and outputs ({}) are inconsistent'.format(n_ex, Y_tmp.shape[0])
                            errlog.exit(msg)
                    else:
                        n_ex = 0
                        if user_init ==0:
                            #msg = 'Error reading json: # of initial DoE should be greater than 0'
                            #errlog.exit(msg)
                            user_init = -1;
                        X_tmp = np.zeros((0, x_dim))
                        Y_tmp = np.zeros((0, y_dim))

                if self.lf_is_model:
                    if self.use_existing_lf:
                        X_tmp_lf = read_txt(self.inpData_lf, errlog)
                        Y_tmp_lf = read_txt(self.outData_lf, errlog)
                        n_ex = X_tmp_lf.shape[0]
                        if self.do_mf:
                            if X_tmp_lf.shape[1] != self.X_lf.shape[1]:
                                msg = 'Error importing input data: dimension inconsistent: high fidelity data have {} RV column(s) but low fidelity model have {}.'.format(
                                    self.X_lf.shape[1], X_tmp_lf.shape[1])
                                errlog.exit(msg)
                            if Y_tmp_lf.shape[1] != self.Y_lf.shape[1]:
                                msg = 'Error importing input data: dimension inconsistent: high fidelity data have {} QoI column(s) but low fidelity model have {}.'.format(
                                    self.Y_lf.shape[1], Y_tmp_lf.shape[1])
                                errlog.exit(msg)
                        if X_tmp_lf.shape[1] != x_dim:
                            msg = 'Error importing input data: dimension inconsistent: have {} RV(s) but have {} column(s).'.format(
                                x_dim, X_tmp_lf.shape[1])
                            errlog.exit(msg)
                        if Y_tmp_lf.shape[1] != y_dim:
                            msg = 'Error importing input data: dimension inconsistent: have {} QoI(s) but have {} column(s).'.format(
                                y_dim, Y_tmp_lf.shape[1])
                            errlog.exit(msg)
                        if n_ex != Y_tmp_lf.shape[0]:
                            msg = 'Error importing input data: numbers of samples of inputs ({}) and outputs ({}) are inconsistent'.format(
                                n_ex, Y_tmp_lf.shape[0])
                            errlog.exit(msg)
                    else:
                        n_ex_lf = 0
                        if user_init_lf == 0:
                             user_init_lf = -1;
                        X_tmp_lf = np.zeros((0, x_dim))
                        Y_tmp_lf = np.zeros((0, y_dim))

                    if user_init_lf < 0:
                        n_init_ref = min(4 * x_dim, thr_count_lf + n_ex_lf - 1, 500)
                        if self.do_parallel:
                            n_init_ref = int(np.ceil(n_init_ref/self.n_processor)*self.n_processor) # Let's not waste resource
                        if n_init_ref > n_ex_lf:
                            n_init_lf = n_init_ref - n_ex_lf
                        else:
                            n_init_lf = 0
                    else:
                        n_init_lf = user_init_lf

                #n_iter_lf = thr_count_lf - n_init_lf

            if self.do_mf:
                if self.mf_case == 'model-model':
                    def FEM_batch(Xs, id_sim):
                        return run_FEM_batch(Xs, id_sim, self.rv_name, self.do_parallel, self.y_dim, self.os_type,
                                             self.run_type, self.pool, t_init, thr_t, runIdx=1)
                    def FEM_batch_lf(Xs, id_sim):
                        return run_FEM_batch(Xs, id_sim, self.rv_name, self.do_parallel, self.y_dim, self.os_type,
                                             self.run_type, self.pool, t_init, thr_t, runIdx=2)

                    self.id_sim_lf = 0
            else:
                def FEM_batch(Xs, id_sim):
                    return run_FEM_batch(Xs, id_sim, self.rv_name, self.do_parallel, self.y_dim, self.os_type, self.run_type, self.pool, t_init, thr_t, runIdx=0)



            # check validity of datafile


            if not self.do_mf:

                if n_ex > 0:
                    #Y_test, self.id_sim = FEM_batch(X_tmp[0, :][np.newaxis], self.id_sim)
                    # TODO : Fix this
                    print(X_tmp[0, :][np.newaxis].shape)
                    X_test, Y_test ,self.id_sim= FEM_batch(X_tmp[0, :][np.newaxis] ,self.id_sim)
                    if np.sum(abs((Y_test - Y_tmp[0, :][np.newaxis]) / Y_test) > 0.01, axis=1) > 0:
                        msg = 'Consistency check failed. Your data is not consistent to your model response. If data is different '
                        errlog.exit(msg)
                    if n_init>0:
                        n_init -= 1
                    else:
                        n_iter -= 1

            if self.do_mf:
                if self.hf_is_model:
                    if n_ex_hf > 0:
                        X_test, Y_test, self.id_sim = FEM_batch(X_tmp[0, :][np.newaxis], self.id_sim)
                        if np.sum(abs((Y_test - Y_tmp[0, :][np.newaxis]) / Y_test) > 0.01, axis=1) > 0:
                            msg = 'Consistency check failed. Your data is not consistent to your model response. If data is different '
                            errlog.exit(msg)
                        if n_init > 0:
                            n_init_hf -= 1
                        else:
                            n_iter_hf -= 1
            #
            # generate initial samples
            #

            if n_init>0:
                U = lhs(x_dim, samples=(n_init))
                X = np.vstack([X_tmp, np.zeros((n_init, x_dim))])
                for nx in range(x_dim):
                    X[n_ex:n_ex+n_init, nx] = U[:, nx] * (self.xrange[nx, 1] - self.xrange[nx, 0]) + self.xrange[nx, 0]
            else:
                X = X_tmp



            if self.do_mf:
                if n_init_lf>0:
                    U = lhs(x_dim, samples=(n_init_lf))
                    self.X_lf = np.vstack([X_tmp_lf, np.zeros((n_init_lf, x_dim))])
                    for nx in range(x_dim):
                        self.X_lf[n_ex_lf:n_ex_lf+n_init_lf, nx] = U[:, nx] * (self.xrange[nx, 1] - self.xrange[nx, 0]) + self.xrange[nx, 0]
                else:
                    self.X_lf = X_tmp_lf

            if sum(abs(self.len / self.xrange[:, 0]) < 1.e-7) > 1:
                msg = 'Error : upperbound and lowerbound should not be the same'
                errlog.exit(msg)

            n_iter = thr_count - n_init

        else:

            n_ex = 0
            thr_NRMSE = 0.02 # default
            thr_t = float('inf')

            #
            # Read sample locations from directory
            #

            X = read_txt(self.inpData,errlog)

            if self.do_mf:
                if X.shape[1] != self.X_hf.shape[1]:
                    msg = 'Error importing input data: dimension inconsistent: high fidelity data have {} RV column(s) but low fidelity model have {}.'.format(
                        self.X_hf.shape[1], X.shape[1])
                    errlog.exit(msg)

            if X.shape[1] != x_dim:
                msg = 'Error importing input data: Number of dimension inconsistent: have {} RV(s) but {} column(s).' \
                    .format(x_dim, X.shape[1])
                errlog.exit(msg)

            self.xrange = np.vstack([np.min(X, axis=0), np.max(X, axis=0)]).T
            self.len = 2 * np.std(X, axis=0)

            thr_count = X.shape[0]
            n_init = thr_count
            n_iter = 0


        # give error

        if thr_count <= 2:
            msg = 'Number of samples should be greater than 2.'
            errlog.exit(msg)


        if do_doe:
            ac = 1  # pre-screening time = time*ac
            ar = 1  # cluster
            n_candi = min(200 * x_dim, 2000)  # candidate points
            n_integ = min(200 * x_dim, 2000)  # integration points
            if user_init > thr_count:
                msg = 'Number of DoE cannot exceed total number of simulation'
                errlog.exit(msg)
        else:
            ac = 1  # pre-screening time = time*ac
            ar = 1  # cluster
            n_candi = 1 # candidate points
            n_integ = 1 # integration points
            user_init = thr_count

        #
        # get y points
        #

        if do_simulation:
            #
            # SimCenter workflow setting
            #
            if os.path.exists('{}/workdir.1'.format(work_dir)):
                is_left = True
                idx = 0

                def change_permissions_recursive(path, mode):
                    for root, dirs, files in os.walk(path, topdown=False):
                        for dir in [os.path.join(root, d) for d in dirs]:
                            os.chmod(dir, mode)
                    for file in [os.path.join(root, f) for f in files]:
                        os.chmod(file, mode)

                while is_left:
                    idx = idx + 1
                    try:
                        if os.path.exists('{}/workdir.{}/workflow_driver.bat'.format(work_dir, idx)):
                            #os.chmod('{}/workdir.{}'.format(work_dir, idx), 777)
                            change_permissions_recursive('{}/workdir.{}'.format(work_dir, idx), 0o777)
                        my_dir = '{}/workdir.{}'.format(work_dir, idx)
                        os.chmod(my_dir, 0o777)
                        shutil.rmtree(my_dir)
                        #shutil.rmtree('{}/workdir.{}'.format(work_dir, idx), ignore_errors=False, onerror=handleRemoveReadonly)

                    except Exception as ex:
                        print(ex)
                        is_left = True
                        break

                print("Cleaned the working directory")
            else:
                print("Work directory is clean")

            if os.path.exists('{}/dakotaTab.out'.format(work_dir)):
                os.remove('{}/dakotaTab.out'.format(work_dir))

            if os.path.exists('{}/inputTab.out'.format(work_dir)):
                os.remove('{}/inputTab.out'.format(work_dir))

            if os.path.exists('{}/outputTab.out'.format(work_dir)):
                os.remove('{}/outputTab.out'.format(work_dir))

            if os.path.exists('{}/SimGpModel.pkl'.format(work_dir)):
                os.remove('{}/SimGpModel.pkl'.format(work_dir))

            if os.path.exists('{}/verif.out'.format(work_dir)):
                os.remove('{}/verif.out'.format(work_dir))

            # func = self.__run_FEM(X,self.id_sim, self.rv_name)

            #
            # Generate initial samples
            #
            t_tmp = time.time()

            X_fem, Y_fem ,self.id_sim= FEM_batch(X[n_ex:, :],self.id_sim)
            Y = np.vstack((Y_tmp,Y_fem))
            X = np.vstack((X[0:n_ex, :],X_fem))

            t_sim_all = time.time() - t_tmp

            if automate_doe:
                self.t_sim_each = t_sim_all / n_init
            else:
                self.t_sim_each = float("inf")

            if self.do_mf:
                if self.mf_case == "model-model":
                    X_fem, Y_fem, self.id_sim = FEM_batch_lf(self.X_lf[n_ex:, :], self.id_sim_lf)
                    self.Y_lf = np.vstack((Y_tmp_lf, Y_fem))
                    self.X_lf = np.vstack((self.X_lf[0:n_ex_lf, :], X_fem))


            #
            # Generate predictive samples
            #
            if self.do_predictive:
                n_pred = 100
                Xt = np.zeros((n_pred, x_dim))
                U = lhs(x_dim, samples=n_pred)
                for nx in range(x_dim):
                    Xt[:, nx] = U[:, nx] * (self.xrange[nx, 1] - self.xrange[nx, 0]) + self.xrange[nx, 0]
                #
                # Yt = np.zeros((n_pred, y_dim))
                # for ns in range(n_pred):
                #     Yt[ns, :],self.id_sim = run_FEM(Xt[ns, :][np.newaxis],self.id_sim, self.rv_name)

                Yt = np.zeros((n_pred, y_dim))
                Xt, Yt ,self.id_sim= FEM_batch(Xt,self.id_sim)

        else:

            #
            # READ SAMPLES FROM DIRECTORY
            #
            Y = read_txt(self.outData,errlog)

            if self.do_mf:
                if Y.shape[1] != self.Y_hf.shape[1]:
                    msg = 'Error importing input data: dimension inconsistent: high fidelity data have {} QoI column(s) but low fidelity model have {}.'.format(
                        self.Y_hf.shape[1], Y.shape[1])
                    errlog.exit(msg)

            if Y.shape[1] != y_dim:
                msg = 'Error importing input data: Number of dimension inconsistent: have {} QoI(s) but {} column(s).' \
                    .format(y_dim, Y.shape[1])
                errlog.exit(msg)

            if X.shape[0] != Y.shape[0]:
                msg = 'Error importing input data: numbers of samples of inputs ({}) and outputs ({}) are inconsistent'.format(X.shape[0], Y.shape[0])
                errlog.exit(msg)

            thr_count  = 0
            self.t_sim_each = float("inf")
        #
        # GP function
        #

        if kernel == 'Radial Basis':
            kr = GPy.kern.RBF(input_dim=x_dim, ARD=True)
        elif kernel == 'Exponential':
            kr = GPy.kern.Exponential(input_dim=x_dim, ARD=True)
        elif kernel == 'Matern 3/2':
            kr = GPy.kern.Matern32(input_dim=x_dim, ARD=True)
        elif kernel == 'Matern 5/2':
            kr = GPy.kern.Matern52(input_dim=x_dim, ARD=True)

        if do_linear:
            kr = kr + GPy.kern.Linear(input_dim=x_dim, ARD=True)

        if not self.do_mf:
            kg = kr
            self.m_list = list()
            for i in range(y_dim):
                self.m_list = self.m_list + [GPy.models.GPRegression(X, Y[:, i][np.newaxis].transpose(), kernel=kg.copy(),normalizer=True)]
                for parname in self.m_list[i].parameter_names():
                    if parname.endswith('lengthscale'):
                        exec('self.m_list[i].' + parname + '=self.len')

        else:
            kgs = emf.kernels.LinearMultiFidelityKernel([kr.copy(), kr.copy()])

            if not self.hf_is_model:
                if not X.shape[1]==self.X_hf.shape[1]:
                    msg = 'Error importing input data: dimension of low ({}) and high ({}) fidelity models (datasets) are inconsistent'.format(X.shape[1], self.X_hf.shape[1])
                    errlog.exit(msg)

            if not self.lf_is_model:
                if not X.shape[1]==self.X_lf.shape[1]:
                    msg = 'Error importing input data: dimension of low ({}) and high ({}) fidelity models (datasets) are inconsistent'.format(X.shape[1], self.X_hf.shape[1])
                    errlog.exit(msg)

            if self.mf_case == 'data-model' or self.mf_case=='data-data':
                X_list, Y_list = emf.convert_lists_to_array.convert_xy_lists_to_arrays([X, self.X_hf], [Y, self.Y_hf])
            elif self.mf_case == 'model-data' or self.mf_case == 'model-model':
                X_list, Y_list = emf.convert_lists_to_array.convert_xy_lists_to_arrays([self.X_lf, X], [self.Y_lf, Y])

            self.m_list = list()
            for i in range(y_dim):
                self.m_list = self.m_list + [GPyMultiOutputWrapper(emf.models.GPyLinearMultiFidelityModel(X_list, Y_list, kernel=kgs.copy(), n_fidelities=2), 2, n_optimization_restarts=15)]


        #
        # Verification measures
        #

        self.NRMSE_hist = np.zeros((1, y_dim), float)
        self.NRMSE_idx = np.zeros((1, 1), int)
        #leng_hist = np.zeros((1, self.m_list[0]._param_array_.shape[0]), int)
        if self.do_predictive:
            self.NRMSE_pred_hist = np.empty((1, y_dim), float)

        #
        # Run DoE
        #

        break_doe = False

        print("======== RUNNING GP DoE ===========")
        exit_code = 'count'  # num iter
        i = 0
        x_new = np.zeros((0,x_dim))
        n_new = 0

        doe_off = False # false if true

        while not doe_off:

            t = time.time()
            if self.doe_method == "random":
                do_cal = True
            elif self.doe_method == "pareto":
                do_cal = True
            elif np.mod(i, self.cal_interval) == 0:
                do_cal = True
            else:
                do_cal = False

            t_tmp = time.time()
            [x_new, self.m_list, err, idx, Y_cv, Y_cv_var] = self.__design_of_experiments(X, Y, ac, ar, n_candi,
                                                                                          n_integ, self.m_list,
                                                                                          do_cal, nugget_opt, do_doe)

            t_doe = time.time() - t_tmp
            print('DoE Time: {:.2f} s'.format(t_doe))

            if automate_doe:
                if t_doe > self.t_sim_each:
                    break_doe = True
                    print('========>> DOE OFF')
                    n_left = n_iter - i
                    break

            if not self.do_mf:
                NRMSE_val = self.__normalized_mean_sq_error(Y_cv, Y)
            else:
                if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                    NRMSE_val = self.__normalized_mean_sq_error(Y_cv, self.Y_hf)
                elif self.mf_case == 'model-data'  or self.mf_case == 'model-model':
                    NRMSE_val = self.__normalized_mean_sq_error(Y_cv, Y)

            self.NRMSE_hist = np.vstack((self.NRMSE_hist, np.array(NRMSE_val)))
            self.NRMSE_idx = np.vstack((self.NRMSE_idx, i))

            if self.do_predictive:
                Yt_pred = np.zeros((n_pred, y_dim))
                for ny in range(y_dim):
                    y_pred_tmp, dummy = self.__predict(self.m_list[ny],Xt)
                    Yt_pred[:, ny] = y_pred_tmp.transpose()
                if self.do_logtransform:
                    Yt_pred = np.exp(Yt_pred)
                NRMSE_pred_val = self.__normalized_mean_sq_error(Yt_pred, Yt)
                self.NRMSE_pred_hist = np.vstack((self.NRMSE_pred_hist, np.array(NRMSE_pred_val)))

            if self.id_sim >= thr_count:
                n_iter = i
                exit_code = 'count'
                doe_off = True
                if not do_cal:
                    break_doe = False
                    n_left = 0
                break

            if np.max(NRMSE_val) < thr_NRMSE:
                n_iter = i
                exit_code = 'accuracy'
                doe_off = True
                if not do_cal:
                    break_doe = False
                    n_left = n_iter - i
                break

            if time.time() - t_init > thr_t - self.calib_time:
                n_iter = i
                exit_code = 'time'
                doe_off = True
                if not do_cal:
                    break_doe = False
                    n_left = n_iter - i
                break

            n_new = x_new.shape[0]
            if not (n_new + self.id_sim < n_init + n_iter +1):
                n_new = n_init + n_iter - self.id_sim
                x_new = x_new[0:n_new, :]

            i = self.id_sim + n_new

            # y_new = np.zeros((n_new, y_dim))
            # for ny in range(n_new):
            #     y_new[ny, :],self.id_sim = run_FEM(x_new[ny, :][np.newaxis],self.id_sim, self.rv_name)
            x_new, y_new, self.id_sim = FEM_batch(x_new,self.id_sim)

            #print(">> {:.2f} s".format(time.time() - t_init))
            X = np.vstack([X, x_new])
            Y = np.vstack([Y, y_new])


        print("======== RUNNING GP Calibration ===========")

        # not used
        if break_doe:
            X_tmp = np.zeros((n_left, x_dim))
            Y_tmp = np.zeros((n_left, y_dim))
            U = lhs(x_dim, samples=n_left)
            for nx in range(x_dim):
                # X[:,nx] = np.random.uniform(xrange[nx,0], xrange[nx,1], (1, n_init))
                X_tmp[:, nx] = U[:, nx] * (self.xrange[nx, 1] - self.xrange[nx, 0]) + self.xrange[nx, 0]

            X_tmp, Y_tmp, self.id_sim = FEM_batch(X_tmp,self.id_sim)

            # for ns in np.arange(n_left):
            #     Y_tmp[ns, :],self.id_sim = run_FEM(X_tmp[ns, :][np.newaxis],self.id_sim, self.rv_name)
            #     print(">> {:.2f} s".format(time.time() - t_init))
            #     if time.time() - t_init > thr_t - self.calib_time:
            #         X_tmp = X_tmp[:ns, :]
            #         Y_tmp = Y_tmp[:ns, :]
            #         break

            X = np.vstack((X, X_tmp))
            Y = np.vstack((Y, Y_tmp))
            do_doe = False

            # if not do_doe:
            #     exit_code = 'count'
            #
            #     do_cal = True
            #     self.t_sim_each = float("inf")  # so that calibration is not terminated in the middle
            #     self.m_list, Y_cv, Y_cv_var = self.__design_of_experiments(X, Y, 1, 1, 1, 1, self.m_list, do_cal,
            #                                                                do_nugget, do_doe)
            #     if not self.do_mf:
            #         NRMSE_val = self.__normalized_mean_sq_error(Y_cv, Y)
            #     else:
            #         NRMSE_val = self.__normalized_mean_sq_error(Y_cv, self.Y_hf)



        sim_time = time.time() - t_init
        n_samp = Y.shape[0]

        # import matplotlib.pyplot as plt
        # if self.x_dim==1:
        #     if self.do_mf:
        #         for ny in range(y_dim):
        #
        #             x_plot = np.linspace(0, 1, 200)[:, np.newaxis]
        #             X_plot = convert_x_list_to_array([x_plot, x_plot])
        #             X_plot_l = X_plot[:len(x_plot)]
        #             X_plot_h = X_plot[len(x_plot):]
        #
        #             lf_mean_lin_mf_model, lf_var_lin_mf_model = self.__predict(self.m_list[ny],X_plot_l)
        #             lf_std_lin_mf_model = np.sqrt(lf_var_lin_mf_model)
        #             hf_mean_lin_mf_model, hf_var_lin_mf_model = self.__predict(self.m_list[ny],X_plot_h)
        #             hf_std_lin_mf_model = np.sqrt(hf_var_lin_mf_model)
        #
        #
        #             plt.plot(x_plot, lf_mean_lin_mf_model);
        #             plt.plot(x_plot, hf_mean_lin_mf_model, '-');
        #             plt.plot(X, Y[:,ny], 'x');
        #             plt.plot(self.X_hf,self.Y_hf[:,ny], 'x');
        #             plt.show()
        #     else:
        #         for ny in range(y_dim):
        #             x_plot = np.linspace(0, 1, 200)[:, np.newaxis]
        #
        #             hf_mean_lin_mf_model, hf_var_lin_mf_model = self.__predict(self.m_list[ny], x_plot)
        #
        #             plt.plot(x_plot, hf_mean_lin_mf_model, '-');
        #             plt.plot(X, Y[:, ny], 'x');
        #             plt.show()
        #
        #

        # plt.plot(Y_cv[:,0], self.Y_hf[:,0], 'x'); plt.show()
        # plt.show()
        # plt.plot(Y_cv[:,1], Y[:,1], 'x')
        # plt.show()
        print('my exit code = {}'.format(exit_code))
        print('1. count = {}'.format(self.id_sim))
        print('2. max(NRMSE) = {}'.format(np.max(NRMSE_val)))
        print('3. time = {:.2f} s'.format(sim_time))

        # for user information
        if do_simulation:
            n_err = 1000
            Xerr = np.zeros((n_err, x_dim))
            U = lhs(x_dim, samples=n_err)
            for nx in range(x_dim):
                Xerr[:, nx] = U[:, nx] * (self.xrange[nx, 1] - self.xrange[nx, 0]) + self.xrange[nx, 0]

            y_pred_var = np.zeros((n_err, y_dim))
            y_data_var = np.zeros((n_err, y_dim))

            for ny in range(y_dim):
                # m_tmp = self.m_list[ny].copy()
                m_tmp = self.m_list[ny]
                if self.do_logtransform:
                    #y_var_val = np.var(np.log(Y[:, ny]))
                    log_mean = np.mean(np.log(Y[:, ny]))
                    log_var = np.var(np.log(Y[:, ny]))
                    y_var_val = np.exp(2*log_mean+log_var)*(np.exp(log_var)-1) # in linear space
                else:
                    y_var_val = np.var(Y[:, ny])

                for ns in range(n_err):
                    y_pred_tmp, y_pred_var_tmp = self.__predict(m_tmp,Xerr[ns, :][np.newaxis])
                    if self.do_logtransform:
                        y_pred_var[ns, ny] = np.exp(2 * y_pred_tmp + y_pred_var_tmp) * (np.exp(y_pred_var_tmp) - 1)
                    else:
                        y_pred_var[ns, ny] = y_pred_var_tmp

                    y_data_var[ns, ny] = y_var_val

                    #for parname in m_tmp.parameter_names():
                    #    if ('Mat52' in parname) and parname.endswith('variance'):
                    #        exec('y_pred_prior_var[ns,ny]=m_tmp.' + parname)

            #error_ratio1_Pr = (y_pred_var / y_pred_prior_var)
            error_ratio2_Pr = (y_pred_var / y_data_var)
            #np.max(error_ratio1_Pr, axis=0)
            np.max(error_ratio2_Pr, axis=0)

            self.perc_thr = np.hstack([np.array([1]), np.arange(10, 1000, 50), np.array([999])])
            error_sorted = np.sort(np.max(error_ratio2_Pr, axis=1), axis=0)
            self.perc_val = error_sorted[self.perc_thr]  # criteria
            self.perc_thr = 1 - (self.perc_thr) * 0.001  # ratio=simulation/sampling

        corr_val = np.zeros((y_dim,))
        R2_val = np.zeros((y_dim,))
        for ny in range(y_dim):
            if not self.do_mf:
                Y_ex = Y[:, ny]
            else:
                if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                    Y_ex = self.Y_hf[:, ny]
                elif self.mf_case == 'model-data' or self.mf_case == 'model-model':
                    Y_ex = Y[:, ny]

            corr_val[ny] = np.corrcoef(Y_ex, Y_cv[:, ny])[0, 1]
            R2_val[ny] = 1 - np.sum(pow(Y_cv[:, ny] - Y_ex, 2)) / np.sum(pow(Y_cv[:, ny] - np.mean(Y_cv[:, ny]), 2))
            if np.var(Y_ex)==0:
                corr_val[ny] = 1
                R2_val[ny] = 0

        self.kernel = kernel
        self.NRMSE_val = NRMSE_val
        self.corr_val = corr_val
        self.R2_val = R2_val
        self.Y_loo = Y_cv
        self.X = X
        self.Y = Y
        self.do_sampling = do_sampling
        self.do_simulation = do_simulation
        self.do_doe = do_doe
        self.do_linear = do_linear

        self.exit_code = exit_code

        self.thr_count = thr_count
        self.thr_NRMSE = thr_NRMSE
        self.thr_t = thr_t

        self.NRMSE_val = NRMSE_val
        self.sim_time = sim_time
        self.n_samp = n_samp
        self.n_sim = self.id_sim

        self.y_loo = Y_cv
        self.y_exa = Y
        self.Y_loo_var = Y_cv_var

        self.rvName = []
        self.rvDist = []
        self.rvVal = []
        for nx in range(x_dim):
            rvInfo = inp["randomVariables"][nx]
            self.rvName = self.rvName + [rvInfo["name"]]
            self.rvDist = self.rvDist + [rvInfo["distribution"]]
            if do_sampling:
                self.rvVal = self.rvVal + [(rvInfo["upperbound"] + rvInfo["lowerbound"]) / 2]
            else:
                self.rvVal = self.rvVal + [np.mean(X[:, nx])]

    def __parameter_calibration(self, m_tmp_list, x_dim, nugget_opt):

        warnings.filterwarnings("ignore")

        t_opt = time.time()
        m_list = list()

        for ny in range(self.y_dim):

            print("y dimension {}:".format(ny))
            nopt = 10

            #
            # previous optimal
            #
            nugget_opt_tmp = nugget_opt

            if not self.do_mf:
                if np.var(m_tmp_list[ny].Y) == 0:
                    nugget_opt_tmp = "Zero"
                    for parname in m_tmp_list[ny].parameter_names():
                        if parname.endswith('variance'):
                            m_tmp_list[ny][parname].constrain_fixed(0)

                m_init = m_tmp_list[ny]
                m_tmp = m_init

                if nugget_opt_tmp == "Optimize":
                    m_tmp['Gaussian_noise.variance'].unfix()
                elif nugget_opt_tmp == "Fixed Values":
                    m_tmp['Gaussian_noise.variance'].constrain_fixed(self.nuggetVal[ny])
                elif nugget_opt_tmp == "Fixed Bounds":
                    m_tmp['Gaussian_noise.variance'].constrain_bounded(self.nuggetVal[ny][0], self.nuggetVal[ny][1])
                elif nugget_opt_tmp == "Zero":
                    m_tmp['Gaussian_noise.variance'].constrain_fixed(0)

                m_tmp.optimize(clear_after_finish=True)
                # m_tmp.optimize_restarts(5)
                max_log_likli = m_tmp.log_likelihood()

                t_unfix = time.time()
                m = m_tmp.copy()

                id_opt = 1
                print('{} among {} Log-Likelihood: {}'.format(1, nopt, m_tmp.log_likelihood()))
                #print('     Calibration time for each: {:.2f} s'.format(time.time() - t_unfix))

                if time.time() - t_unfix > self.t_sim_each:
                    nopt = 1

                #
                # initial try
                #

                for parname in m_tmp.parameter_names():
                    if parname.endswith('lengthscale'):
                        exec('m_tmp.' + parname + '=self.len')

                if nugget_opt_tmp == "Optimize":
                    m_tmp['Gaussian_noise.variance'].unfix()
                elif nugget_opt_tmp == "Fixed Values":
                    m_tmp['Gaussian_noise.variance'].constrain_fixed(self.nuggetVal[ny])
                elif nugget_opt_tmp == "Fixed Bounds":
                    m_tmp['Gaussian_noise.variance'].constrain_bounded(self.nuggetVal[ny][0], self.nuggetVal[ny][1])
                elif nugget_opt_tmp == "Zero":
                    m_tmp['Gaussian_noise.variance'].constrain_fixed(0)

                m_tmp.optimize(clear_after_finish=True)
                # m_tmp.optimize_restarts(5)

                t_unfix = time.time()
                if m_tmp.log_likelihood() > max_log_likli:
                    max_log_likli = m_tmp.log_likelihood()
                    m = m_tmp.copy()

                id_opt = 1
                print('{} among {} Log-Likelihood: {}'.format(2, nopt, m_tmp.log_likelihood()))
                #print('     Calibration time for each: {:.2f} s'.format(time.time() - t_unfix))

                if time.time() - t_unfix > self.t_sim_each:
                    nopt = 1

                for no in range(nopt - 2):
                    # m_tmp=m.copy()
                    # m.randomize()
                    for parname in m_tmp.parameter_names():
                        if parname.endswith('lengthscale'):
                            if math.isnan(m.log_likelihood()):
                                exec('m_tmp.' + parname + '=np.random.exponential(1, (1, x_dim)) * m_init.' + parname)
                            else:
                                exec('m_tmp.' + parname + '=np.random.exponential(1, (1, x_dim)) * m.' + parname)

                    if nugget_opt_tmp == "Optimize":
                        m_tmp['Gaussian_noise.variance'].unfix()
                    elif nugget_opt_tmp == "Fixed Values":
                        m_tmp['Gaussian_noise.variance'].constrain_fixed(self.nuggetVal[ny])
                    elif nugget_opt_tmp == "Fixed Bounds":
                        m_tmp['Gaussian_noise.variance'].constrain_bounded(self.nuggetVal[ny][0], self.nuggetVal[ny][1])
                    elif nugget_opt_tmp == "Zero":
                        m_tmp['Gaussian_noise.variance'].constrain_fixed(0)

                    t_fix = time.time()
                    try:
                        m_tmp.optimize()
                        # m_tmp.optimize_restarts(5)

                    except Exception as ex:
                        print("OS error: {0}".format(ex))

                    print('{} among {} Log-Likelihood: {}'.format(no + 3, nopt, m_tmp.log_likelihood()))
                    #print('     Calibration time for each: {:.2f} s'.format(time.time() - t_fix))

                    if m_tmp.log_likelihood() > max_log_likli:
                        max_log_likli = m_tmp.log_likelihood()
                        m = m_tmp.copy()
                        id_opt = no

                    if time.time() - t_unfix > self.t_sim_each:
                        nopt = 2 + no
                        break

                if math.isinf(-max_log_likli) or math.isnan(-max_log_likli):
                    #msg = "Error GP optimization failed, perhaps QoI values are zero."
                    if np.var(m_tmp.Y) != 0:
                        msg = "Error GP optimization failed for QoI #{}".format(ny+1)
                        self.errlog.exit(msg)

                m_list = m_list + [m]
                print(m)
            else:


                if nugget_opt_tmp == "Optimize":
                    m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise.unfix()
                    m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise_1.unfix()

                elif nugget_opt_tmp == "Fixed Values":
                    m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise.constrain_fixed(self.nuggetVal[ny])
                    m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise_1.constrain_fixed(self.nuggetVal[ny])

                elif nugget_opt_tmp == "Fixed Bounds":
                    m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise.constrain_bounded(self.nuggetVal[ny][0], self.nuggetVal[ny][1])
                    m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise_1.constrain_bounded(self.nuggetVal[ny][0], self.nuggetVal[ny][1])

                elif nugget_opt_tmp == "Zero":
                    m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise.constrain_fixed(0)
                    m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise_1.constrain_fixed(0)
                #
                # if not do_nugget:
                #     m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise.fix(0)
                #     m_tmp_list[ny].gpy_model.mixed_noise.Gaussian_noise_1.fix(0)

                m_tmp_list[ny].optimize()
                nopt = 5
                id_opt = 0

        self.calib_time = (time.time() - t_opt) * round(10 / nopt)
        print('     Calibration time: {:.2f} s, id_opt={}'.format(self.calib_time, id_opt))

        return m_tmp_list

    def __design_of_experiments(self, X, Y, ac, ar, n_candi, n_integ, pre_m_list, do_cal, nugget_opt, do_doe):

        # do log transform
        if self.do_logtransform:

            if np.min(Y)<0:
                msg = 'Error running SimCenterUQ. Response contains negative values. Please uncheck the log-transform option in the UQ tab'
                errlog.exit(msg)
            Y = np.log(Y)

            if self.do_mf:

                if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                    if np.min(self.Y_hf)<0:
                        msg = 'Error running SimCenterUQ. Response contains negative values. Please uncheck the log-transform option in the UQ tab'
                        errlog.exit(msg)
                    self.Y_hf = np.log(self.Y_hf)
                elif self.mf_case == 'mode-data':
                    if np.min(self.Y_lf) < 0:
                        msg = 'Error running SimCenterUQ. Response contains negative values. Please uncheck the log-transform option in the UQ tab'
                        errlog.exit(msg)
                    self.Y_lf = np.log(self.Y_lf)

        r = 1  # adaptively

        y_dim = Y.shape[1]
        x_dim = X.shape[1]

        m_tmp_list = pre_m_list

        for i in range(y_dim):
            if not self.do_mf:
                m_tmp_list[i].set_XY(X, Y[:, i][np.newaxis].transpose())
            else:

                if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                    X_list_tmp, Y_list_tmp = emf.convert_lists_to_array.convert_xy_lists_to_arrays([X, self.X_hf],
                                                                                                   [Y[:, i][np.newaxis].transpose(), self.Y_hf[:, i][np.newaxis].transpose()])
                elif self.mf_case == 'model-data' or self.mf_case == 'model-model':
                    X_list_tmp, Y_list_tmp = emf.convert_lists_to_array.convert_xy_lists_to_arrays([self.X_lf, X],
                                                                                                   [self.Y_lf[:, i][np.newaxis].transpose(),Y[:, i][np.newaxis].transpose()])

                m_tmp_list[i].set_data(X=X_list_tmp,Y=Y_list_tmp)

        if do_cal:
            m_list = self.__parameter_calibration(m_tmp_list, x_dim, nugget_opt)
        else:
            m_list = m_tmp_list.copy()

        #
        # cross validation errors
        #
        Y_pred, Y_pred_var, e2 =  self.__get_cross_validation(X,Y,m_list)


        if self.do_logtransform:

            mu = Y_pred
            sig2 = Y_pred_var

            median = np.exp(mu)
            mean = np.exp(mu + sig2/2)
            var = np.exp(2*mu + sig2)*(np.exp(sig2)-1)

            Y_pred = median
            Y_pred_var = var

            if self.do_mf:
                if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                    self.Y_hf = np.exp(self.Y_hf)
                elif self.mf_case == 'model-data' or self.mf_case == 'model-model':
                    self.Y_lf = np.exp(self.Y_lf)

        if not do_doe:
            return 0, m_list, 0, 0, Y_pred, Y_pred_var
        #
        # candidates of DoE
        #

        y_var = np.var(Y, axis=0)  # normalization
        y_idx = np.argmax(np.sum(e2 / y_var, axis=0))  # dimension of interest

        m_tmp_list = m_list.copy()
        m_idx = m_tmp_list[y_idx]

        #
        # SCREENING score_tmp function of each candidate
        #
        nc1 = round(n_candi)

        self.doe_method = self.doe_method.lower()
        if self.doe_method == "pareto":

            #
            # Initial candidates
            #

            xc1 = np.zeros((nc1, x_dim))
            for nx in range(x_dim):
                xc1[:, nx] = np.random.uniform(self.xrange[nx, 0], self.xrange[nx, 1], (1, nc1))  # LHS

            nq = round(n_integ)
            xq = np.zeros((nq, x_dim))
            for nx in range(x_dim):
                xq[:, nx] = np.random.uniform(self.xrange[nx, 0], self.xrange[nx, 1], (1, nq))
            #
            # Lets Do Pareto
            #

            yc1_pred, yc1_var = self.__predict(m_idx, xc1)  # use only variance
            score1 = np.zeros(yc1_pred.shape)
            cri1 = np.zeros(yc1_pred.shape)
            cri2 = np.zeros(yc1_pred.shape)
            # TODO: is this the best?
            ll = self.xrange[:, 1] - self.xrange[:, 0]
            for i in range(nc1):
                if not self.do_mf:
                    wei = self.weights_node2(xc1[i, :], X, ll)
                    #phi = e2[closest_node(xc1[i, :], X, ll)]
                    #phi = e2[self.__closest_node(xc1[i, :], X)]
                else:
                    if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                        wei = self.weights_node2(xc1[i, :], self.X_hf, ll)
                        #phi = e2[closest_node(xc1[i, :], self.X_hf, ll)]
                        #phi = e2[self.__closest_node(xc1[i, :], self.X_hf)]
                    elif self.mf_case == 'model-data' or self.mf_case == 'model-model':
                        wei = self.weights_node2(xc1[i, :], X, ll)
                        #phi = e2[closest_node(xc1[i, :], X, ll)]
                        #phi = e2[self.__closest_node(xc1[i, :], X)]

                #cri1[i] = yc1_var[i]
                cri2[i] = sum(e2[:, y_idx] / Y_pred_var[:, y_idx] * wei.T)
                #cri2[i] = pow(phi[y_idx],r)

            VOI = np.zeros(yc1_pred.shape)
            for i in range(nc1):
                pdfvals = m_idx.kern.K(np.array([xq[i]]), xq)**2/m_idx.kern.K(np.array([xq[0]]))**2
                VOI[i] = np.mean(pdfvals)*np.prod(np.diff(self.xrange,axis=1)) # * np.prod(np.diff(self.xrange))
                cri1[i] = yc1_var[i] * VOI[i]

            cri1 = (cri1-np.min(cri1))/(np.max(cri1)-np.min(cri1))
            cri2 = (cri2-np.min(cri2))/(np.max(cri2)-np.min(cri2))

            logcrimi1 = np.log(cri1[:, 0])
            logcrimi2 = np.log(cri2[:, 0])


            idx_pareto_front = list()
            rankid = np.zeros(nc1)
            varRank = np.zeros(nc1)
            biasRank = np.zeros(nc1)
            for id in range(nc1):
                idx_tmp = np.argwhere((logcrimi1 >= logcrimi1[id]) * (logcrimi2 >= logcrimi2[id]))
                varRank[id] = np.sum((logcrimi1 >= logcrimi1[id]))
                biasRank[id] = np.sum((logcrimi2 >= logcrimi2[id]))
                rankid[id] = idx_tmp.size

            idx_rank = np.argsort(rankid)
            sort_rank = np.sort(rankid)
            num_1rank = np.sum(rankid==1)
            idx_1rank = list((np.argwhere(rankid==1)).flatten())
            npareto = 4

            if num_1rank < self.cal_interval:
                prob = np.ones((nc1,))
                prob[list(rankid==1)]=0
                prob=prob/sum(prob)
                idx_pareto = idx_1rank + list(np.random.choice(nc1, self.cal_interval-num_1rank, p=prob))
            else:
                idx_pareto_candi = idx_1rank.copy()
                X_tmp = X
                Y_tmp = Y[:,y_idx][np.newaxis].T
                m_tmp = m_idx.copy()

                # get MMSEw
                score = np.squeeze(cri1*cri2)
                score_candi = score[idx_pareto_candi]
                best_local = np.argsort(-score_candi)[0]
                best_global = idx_1rank[best_local]

                idx_pareto_new = [best_global]
                del idx_pareto_candi[best_local]

                for i in range(self.cal_interval-1):
                    X_tmp = np.vstack([X_tmp, xc1[best_global, :][np.newaxis]])
                    Y_tmp = np.vstack([Y_tmp, np.array([[0]]) ]) # any variables
                    m_tmp.set_XY(X=X_tmp, Y=Y_tmp)
                    dummy, Yq_var = m_tmp.predict(xc1[idx_pareto_candi, :])
                    cri1 = Yq_var * VOI[idx_pareto_candi]
                    cri1 = (cri1 - np.min(cri1)) / (np.max(cri1) - np.min(cri1))
                    score_tmp = cri1 * cri2[idx_pareto_candi] # only update the variance

                    best_local = np.argsort(-np.squeeze(score_tmp))[0]
                    best_global = idx_pareto_candi[best_local]
                    idx_pareto_new = idx_pareto_new + [best_global]
                    del idx_pareto_candi[best_local]

                    #score_tmp = Yq_var * cri2[idx_pareto_left]/Y_pred_var[closest_node(xc1[i, :], X, self.m_list, self.xrange)]

            #idx_pareto = list(idx_rank[0:self.cal_interval])
                idx_pareto = idx_pareto_new

            update_point = xc1[idx_pareto, :]
            update_IMSE = 0
                    
            # import matplotlib.pyplot as plt
            # plt.plot(logcrimi1, logcrimi2, 'x');plt.plot(logcrimi1[idx_pareto], logcrimi2[idx_pareto], 'x'); plt.show()
            # plt.plot(m_idx.X[:,0], m_idx.X[:,1], 'x'); plt.show()
            # plt.plot(X[:, 0],X[:, 1], 'ro');           
            # plt.scatter(xc1[:,0], xc1[:,1], c=cri2); plt.plot(xc1[rankid==0,0], xc1[rankid==0,1], 'rx'); plt.show()
            # plt.scatter(xc1[:,0], xc1[:,1], c=cri2); plt.plot(update_point[:,0], update_point[:,1], 'rx'); plt.show()     
            # plt.scatter(xc1[:, 0], xc1[:, 1], c=cri2); plt.show()
            #
            '''
            idx_pareto = list()
            for id in range(nc1):
                idx_tmp = np.argwhere(logcrimi2 >= logcrimi2[id])
                if np.sum(logcrimi1[idx_tmp[:, 0]] >= logcrimi1[id]) == 1:
                    idx_pareto = idx_pareto + [id]
                    
            if len(idx_pareto) == 0:
                idx_pareto = np.arange(self.cal_interval)

            if len(idx_pareto) > self.cal_interval:
                random_indices = random.sample(range(len(idx_pareto)), self.cal_interval)  # get 2 random indices
                idx_pareto2 = np.asarray(random_indices)
                idx_pareto = np.asarray(idx_pareto)
                idx_pareto = list(idx_pareto[idx_pareto2[0:self.cal_interval]])
            '''

        elif self.doe_method == "imsew":


            nq = round(n_integ)
            m_stack = m_idx.copy()
            X_stack = X
            Y_stack = Y

            update_point = np.zeros((self.cal_interval,self.x_dim))
            update_IMSE = np.zeros((self.cal_interval,1))

            #
            # Initial candidates
            #
            for ni in range(self.cal_interval):

                #
                # Initial candidates
                #

                xc1 = np.zeros((nc1, x_dim))
                for nx in range(x_dim):
                    xc1[:, nx] = np.random.uniform(self.xrange[nx, 0], self.xrange[nx, 1], (1, nc1))  # LHS

                xq = np.zeros((nq, x_dim))
                for nx in range(x_dim):
                    xq[:, nx] = np.random.uniform(self.xrange[nx, 0], self.xrange[nx, 1], (1, nq))

                #TODO: is diff(xrange) the best?
                ll = self.xrange[:, 1] - self.xrange[:, 0]
                phiq = np.zeros((nq, y_dim))
                for i in range(nq):
                    phiq[i,:] = e2[closest_node(xq[i, :], X, ll)]

                phiqr = pow(phiq[:, y_idx], r)

                if self.do_parallel:
                    tmp = time.time()
                    iterables = ((m_stack.copy(), xc1[i,:][np.newaxis], xq, phiqr, i) for i in range(nc1))
                    result_objs = list(self.pool.starmap(imse, iterables))
                    IMSEc1 = np.zeros(nc1)
                    for IMSE_val, idx in result_objs:
                        IMSEc1[idx] = IMSE_val
                    print("IMSE: finding the next DOE {} in a parallel way.. time = {}".format(ni,time.time() -tmp)) # 7s # 3-4s
                else:
                    tmp = time.time()
                    phiqr = pow(phiq[:, y_idx], r)
                    IMSEc1 = np.zeros(nc1)
                    for i in range(nc1):
                        IMSEc1[i], dummy = imse(m_stack.copy(), xc1[i,:][np.newaxis], xq, phiqr, i)
                    print("IMSE: finding the next DOE {} in a serial way.. time = {}".format(ni,time.time() -tmp)) # 4s

                new_idx = np.argmin(IMSEc1, axis=0)
                x_point = xc1[new_idx, :][np.newaxis]

                X_stack = np.vstack([X_stack, x_point])
                Y_stack = np.zeros((Y_stack.shape[0] + 1, Y.shape[1]))  # any variables
                m_stack.set_XY(X=X_stack, Y=Y_stack)
                update_point[ni, :] = x_point
                update_IMSE[ni, :] = IMSEc1[new_idx]

            # import matplotlib.pyplot as plt; plt.scatter(xc1[:,0],xc1[:,1],c = IMSEc1); plt.show()
            # import matplotlib.pyplot as plt; plt.scatter(xc1[:,0],xc1[:,1],c = IMSEc1); plt.plot(update_point[:,0],update_point[:,1],'x'); plt.show()     
            # import matplotlib.pyplot as plt; plt.scatter(X_stack[:,0],X_stack[:,1]); plt.show()
            '''
            
            nc1 = round(n_candi)
            xc1 = np.zeros((nc1, x_dim))
            for nx in range(x_dim):
            xc1[:, nx] = np.random.uniform(self.xrange[nx, 0], self.xrange[nx, 1], (1, nc1))  # LHS
            
            yc1_pred, yc1_var = self.__predict(m_idx, xc1)  # use only variance
            score1 = np.zeros(yc1_pred.shape)
            cri1 = np.zeros(yc1_pred.shape)
            cri2 = np.zeros(yc1_pred.shape)
            for i in range(nc1):
                if not self.do_mf:
                    phi = e2[self.__closest_node(xc1[i, :], X)]
                else:
                    phi = e2[self.__closest_node(xc1[i, :], self.X_hf)]

                score1[i] = yc1_var[i] * pow(phi[y_idx], r)
                cri1[i] = yc1_var[i]
                cri2[i] = pow(phi[y_idx], r)
                
            sort_idx_score1 = np.argsort(-score1.T)  # (-) sign to make it descending order
            nc2 = round(nc1 * ac)
            xc2 = xc1[sort_idx_score1[0, 0:nc2], :]
            score2 = score1[sort_idx_score1[0, 0:nc2]]
        
            nc3 = round(nc2 * ar)
            if ar != 1:

                xc2_norm = np.zeros((nc2, x_dim))
                for nx in range(x_dim):
                    xc2_norm[:, nx] = (xc2[:, nx] - self.xrange[nx, 0]) / (
                                self.xrange[nx, 1] - self.xrange[nx, 0])  # additional weights?

                # n_clusters =1
                km_model = KMeans(n_clusters=max(1, nc3))
                km_model.fit(xc2_norm)
                idx_cluster = km_model.predict(xc2_norm)
                global_idx_cluster = np.zeros((nc3, 1), dtype=np.int64)
                for i in range(nc3):
                    ith_cluster_comps = np.where(idx_cluster == i)[0]
                    idx = np.argsort(-score2[ith_cluster_comps].T)[0][0]
                    global_idx_cluster[i, 0] = ith_cluster_comps[idx]

                xc3 = xc2[global_idx_cluster.T, :][0]
                score3 = score2[global_idx_cluster.T][0]
            else:
                xc3 = xc2
                score3 = score2
            #
            # get IMSE
            #

            nq = round(n_integ)

            xq = np.zeros((nq, x_dim))
            for nx in range(x_dim):
                xq[:, nx] = np.random.uniform(self.xrange[nx, 0], self.xrange[nx, 1], (1, nq))

            phi = np.zeros((nq, y_dim))

            for i in range(nq):
                phi[i, :] = e2[self.__closest_node(xq[i, :], X)]

            IMSE = np.zeros((nc3,))

            m_tmp = m_idx.copy()
            for i in range(nc3):
                X_tmp = np.vstack([X, xc3[i, :][np.newaxis]])
                Y_tmp = np.zeros((Y.shape[0] + 1, Y.shape[1]))  # any variables
                m_tmp.set_XY(X=X_tmp, Y=Y_tmp)
                dummy, Yq_var = m_tmp.predict(xq)

                IMSE[i] = 1 / nq * sum(pow(phi[:, y_idx], r) * Yq_var.T[0])

            new_idx = np.argmin(IMSE, axis=0)
            print(np.min(IMSE))

            update_point = xc3[new_idx, :][np.newaxis]
            update_IMSE = IMSE[new_idx]
            
            '''

        elif self.doe_method == "random":

            update_point = xc1[0:self.cal_interval, :]
            update_IMSE = 0

        elif self.doe_method == "mmse":
            sort_idx_score1 = np.argsort(-cri1.T)  # (-) sign to make it descending order
            nc2 = round(nc1 * ac)
            xc2 = xc1[sort_idx_score1[0, 0:nc2], :]

            update_point = xc2[0:1, :]
            update_IMSE = 0

        elif self.doe_method == "mmsew":

            #
            # Initial candidates
            #
            xc1 = np.zeros((nc1, x_dim))
            for nx in range(x_dim):
                xc1[:, nx] = np.random.uniform(self.xrange[nx, 0], self.xrange[nx, 1], (1, nc1))  # LHS

            m_stack = m_idx.copy()
            ll = self.xrange[:, 1] - self.xrange[:, 0]
            phic = np.zeros((nc1, y_dim))
            for i in range(nc1):
                phic[i, :] = e2[closest_node(xc1[i, :], X, ll)]

            phicr = pow(phic[:, y_idx], r)

            X_stack = X
            Y_stack = Y

            update_point = np.zeros((self.cal_interval,self.x_dim))
            update_IMSE = np.zeros((self.cal_interval,1))

            for ni in range(self.cal_interval):
                yc1_pred, yc1_var = m_stack.predict(xc1)  # use only variance
                MMSEc1 = yc1_var.flatten() * phicr.flatten()


                new_idx = np.argmax(MMSEc1, axis=0)
                x_point = xc1[new_idx, :][np.newaxis]

                X_stack = np.vstack([X_stack, x_point])
                Y_stack = np.zeros((Y_stack.shape[0] + 1, Y.shape[1]))  # any variables
                m_stack.set_XY(X=X_stack, Y=Y_stack)
                update_point[ni, :] = x_point
                update_IMSE[ni, :] = MMSEc1[new_idx]

        else:
            msg = 'Error running SimCenterUQ: cannot identify the doe method <' + self.doe_method + '>'
            errlog.exit(msg)

        return update_point, m_list, update_IMSE, y_idx, Y_pred, Y_pred_var

    def __normalized_mean_sq_error(self, yp, ye):
        nt = yp.shape[0]
        data_bound = (np.max(ye, axis=0) - np.min(ye, axis=0))
        RMSE = np.sqrt(1 / nt * np.sum(pow(yp - ye, 2), axis=0))
        NRMSE =RMSE/data_bound
        NRMSE[np.argwhere((data_bound ==0))]=0
        return NRMSE

    def __closest_node(self, node, nodes):
        nodes = np.asarray(nodes)
        deltas = nodes - node

        deltas_norm = np.zeros(deltas.shape)
        for nx in range(self.x_dim):
            deltas_norm[:, nx] = (deltas[:, nx]) / (self.xrange[nx, 1] - self.xrange[nx, 0])  # additional weights?

        # np.argmin(np.sum(pow(deltas_norm,2),axis=1))
        dist_2 = np.einsum('ij,ij->i', deltas_norm, deltas_norm)
        return np.argmin(dist_2)

    def __from_XY_into_list(self, X, Y):
        x_list = list()
        y_list = list()
        for i in range(Y.shape[1]):
            x_list = x_list + [X, ]
            y_list = y_list + [Y[:, [i, ]], ]
        return x_list, y_list

    def __predict(self, m, X):

        if not self.do_mf:
            return m.predict(X)
        else:
            if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                X_list = convert_x_list_to_array([X, X])
                X_list_l = X_list[:X.shape[0]]
                X_list_h = X_list[X.shape[0]:]
                return m.predict(X_list_h)
            elif self.mf_case == 'model-data' or self.mf_case == 'model-model':
                #return m.predict(X)
                X_list = convert_x_list_to_array([X, X])
                X_list_l = X_list[:X.shape[0]]
                X_list_h = X_list[X.shape[0]:]
                return m.predict(X_list_h)



    def __get_cross_validation(self,X,Y,m_list):

        if not self.do_mf:
            e2 = np.zeros(Y.shape)
            Y_pred = np.zeros(Y.shape)
            Y_pred_var = np.zeros(Y.shape)
            for ny in range(Y.shape[1]):
                m_tmp = m_list[ny].copy()
                for ns in range(X.shape[0]):
                    X_tmp = np.delete(X, ns, axis=0)
                    Y_tmp = np.delete(Y, ns, axis=0)
                    m_tmp.set_XY(X=X_tmp, Y=Y_tmp[:, ny][np.newaxis].transpose())
                    x_loo = X[ns, :][np.newaxis]
                    # Y_pred_tmp, Y_err_tmp = m_tmp.predict(x_loo)
                    Y_pred_tmp, Y_err_tmp = self.__predict(m_tmp,x_loo)
                    Y_pred[ns, ny] = Y_pred_tmp
                    Y_pred_var[ns, ny] = Y_err_tmp
                    e2[ns, ny] = pow((Y_pred[ns, ny] - Y[ns, ny]), 2)  # for nD outputs


        else:
            if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                e2 = np.zeros(self.Y_hf.shape)
                Y_pred = np.zeros(self.Y_hf.shape)
                Y_pred_var = np.zeros(self.Y_hf.shape)

                for ny in range(Y.shape[1]):
                    m_tmp =  deepcopy(m_list[ny])
                    for ns in range(self.X_hf.shape[0]):
                        X_hf_tmp = np.delete(self.X_hf, ns, axis=0)
                        Y_hf_tmp = np.delete(self.Y_hf, ns, axis=0)
                        X_list_tmp, Y_list_tmp = emf.convert_lists_to_array.convert_xy_lists_to_arrays([X, X_hf_tmp],
                                                                                                       [Y[:, ny][np.newaxis].transpose(), Y_hf_tmp[:, ny][np.newaxis].transpose()])
                        m_tmp.set_data(X=X_list_tmp, Y=Y_list_tmp)
                        x_loo = self.X_hf[ns][np.newaxis]
                        Y_pred_tmp, Y_err_tmp = self.__predict(m_tmp,x_loo)
                        Y_pred[ns,ny] = Y_pred_tmp
                        Y_pred_var[ns,ny] = Y_err_tmp
                        e2[ns,ny] = pow((Y_pred[ns,ny] - self.Y_hf[ns,ny]), 2)  # for nD outputs

            elif self.mf_case == 'model-data' or self.mf_case == 'model-model':
                e2 = np.zeros(Y.shape)
                Y_pred = np.zeros(Y.shape)
                Y_pred_var = np.zeros(Y.shape)

                for ny in range(Y.shape[1]):
                    m_tmp = deepcopy(m_list[ny])
                    for ns in range(X.shape[0]):
                        X_tmp = np.delete(X, ns, axis=0)
                        Y_tmp = np.delete(Y, ns, axis=0)
                        X_list_tmp, Y_list_tmp = emf.convert_lists_to_array.convert_xy_lists_to_arrays([self.X_lf, X_tmp],
                                                                                                       [self.Y_lf[:, ny][np.newaxis].transpose(), Y_tmp[:, ny][np.newaxis].transpose()])
                        m_tmp.set_data(X=X_list_tmp, Y=Y_list_tmp)
                        #x_loo = np.hstack((X[ns], 1))[np.newaxis]
                        x_loo = X[ns][np.newaxis]
                        Y_pred_tmp, Y_err_tmp = self.__predict(m_tmp,x_loo)
                        Y_pred[ns,ny] = Y_pred_tmp
                        Y_pred_var[ns,ny] = Y_err_tmp
                        e2[ns,ny] = pow((Y_pred[ns,ny] - Y[ns,ny]), 2)  # for nD outputs

        return Y_pred, Y_pred_var, e2

    def term(self):
        if self.do_parallel:
            if self.run_type != "runningLocal":
                print("RUNNING SUCCESSFUL")
                self.world.Abort(0) # to prevent deadlock


    def save_model(self, filename):
        import json

        with open(self.work_dir + '/' + filename + '.pkl', 'wb') as file:
            pickle.dump(self.m_list, file)
            # json.dump(self.m_list, file)


        header_string_x = ' ' + ' '.join([str(elem) for elem in self.rv_name]) + ' '
        header_string_y = ' ' + ' '.join([str(elem) for elem in self.g_name])
        header_string = header_string_x + header_string_y

        if not self.do_mf:
            xy_data = np.concatenate((np.asmatrix(np.arange(1,  self.X.shape[0] + 1)).T, self.X, self.Y), axis=1)
        else:
            if not self.hf_is_model:
                xy_data = np.concatenate((np.asmatrix(np.arange(1, self.X_hf.shape[0] + 1)).T, self.X_hf, self.Y_hf), axis=1)
            else:
                xy_data = np.concatenate((np.asmatrix(np.arange(1, self.X.shape[0] + 1)).T, self.X, self.Y), axis=1)
        np.savetxt(self.work_dir + '/dakotaTab.out', xy_data, header=header_string, fmt='%1.4e', comments='%')
        np.savetxt(self.work_dir + '/inputTab.out', self.X, header=header_string_x, fmt='%1.4e', comments='%')
        np.savetxt(self.work_dir + '/outputTab.out', self.Y, header=header_string_y, fmt='%1.4e', comments='%')

        y_ub = np.zeros(self.Y_loo.shape)
        y_lb = np.zeros(self.Y_loo.shape)


        if not self.do_logtransform:
            for ny in range(self.y_dim):
                y_lb[:,ny] = norm.ppf(0.05, loc=self.Y_loo[:, ny],
                                                                  scale=np.sqrt(self.Y_loo_var[:, ny])).tolist()
                y_ub[:, ny] = norm.ppf(0.95, loc=self.Y_loo[:, ny],
                                                                  scale=np.sqrt(self.Y_loo_var[:, ny])).tolist()
        else:
            for ny in range(self.y_dim):
                mu = np.log(self.Y_loo[:, ny])
                sig = np.sqrt(np.log(self.Y_loo_var[:, ny] / pow(self.Y_loo[:, ny], 2) + 1))
                y_lb[:,ny] = lognorm.ppf(0.05, s=sig, scale=np.exp(mu)).tolist()
                y_ub[:, ny] = lognorm.ppf(0.95, s=sig, scale=np.exp(mu)).tolist()

        xy_sur_data = np.hstack((xy_data,self.Y_loo,y_lb,y_ub,self.Y_loo_var))
        g_name_sur =  self.g_name
        header_string_sur = header_string + " " + ".median ".join(
                g_name_sur) + ".median " + ".q5 ".join(g_name_sur) + ".q5 " + ".q95 ".join(
                g_name_sur) + ".q95 " + ".var ".join(g_name_sur) + ".var"

        np.savetxt(self.work_dir + '/surrogateTab.out', xy_sur_data, header=header_string_sur, fmt='%1.4e', comments='%')



        results = {}

        results["doSampling"] = self.do_sampling
        results["doSimulation"] = self.do_simulation
        results["doDoE"] = self.do_doe
        results["doLogtransform"] = self.do_logtransform
        results["doLinear"] = self.do_linear
        results["doMultiFidelity"] = self.do_mf
        results["kernName"] = self.kernel
        results["terminationCode"] = self.exit_code
        results["thrNRMSE"] = self.thr_NRMSE
        results["valSamp"] = self.n_samp
        results["valSim"] = self.n_sim
        results["valTime"] = self.sim_time
        results["xdim"] = self.x_dim
        results["ydim"] = self.y_dim
        results["xlabels"] = self.rv_name
        results["ylabels"] = self.g_name
        results["yExact"] = {}
        results["yPredict"] = {}
        results["valNugget"] = {}
        results["valNRMSE"] = {}
        results["valR2"] = {}
        results["valCorrCoeff"] = {}
        results["yPredict_CI_lb"] = {}
        results["yPredict_CI_ub"] = {}
        results["xExact"] = {}

        for nx in range(self.x_dim):
            results["xExact"][self.rv_name[nx]] = self.X[:, nx].tolist()

        for ny in range(self.y_dim):
            if not self.do_mf:
                results["yExact"][self.g_name[ny]] = self.Y[:, ny].tolist()
            else:
                if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                    results["yExact"][self.g_name[ny]] = self.Y_hf[:, ny].tolist()
                elif self.mf_case == 'model-data' or self.mf_case == 'model-model':
                    results["yExact"][self.g_name[ny]] = self.Y[:, ny].tolist()

            results["yPredict"][self.g_name[ny]] = self.Y_loo[:, ny].tolist()

            if not self.do_logtransform:
                #results["yPredict_CI_lb"][self.g_name[ny]] = self.Y_loo[:, ny].tolist()+2*np.sqrt(self.Y_loo_var[:, ny]).tolist()
                #results["yPredict_CI_lb"][self.g_name[ny]] = self.Y_loo[:, ny].tolist()-2*np.sqrt(self.Y_loo_var[:, ny]).tolist()

                results["yPredict_CI_lb"][self.g_name[ny]] = norm.ppf(0.25, loc = self.Y_loo[:, ny] , scale = np.sqrt(self.Y_loo_var[:, ny])).tolist()
                results["yPredict_CI_ub"][self.g_name[ny]] = norm.ppf(0.75, loc = self.Y_loo[:, ny] , scale = np.sqrt(self.Y_loo_var[:, ny])).tolist()

            else:

                mu = np.log(self.Y_loo[:, ny] )
                sig = np.sqrt(np.log(self.Y_loo_var[:, ny]/pow(self.Y_loo[:, ny] ,2)+1))

                results["yPredict_CI_lb"][self.g_name[ny]] =  lognorm.ppf(0.25, s = sig, scale = np.exp(mu)).tolist()
                results["yPredict_CI_ub"][self.g_name[ny]] =  lognorm.ppf(0.75, s = sig, scale = np.exp(mu)).tolist()



            # if self.do_logtransform:
            #         log_mean = 0
            #         log_var = float(self.m_list[ny]['Gaussian_noise.variance']) # nugget in log-space
            #         nuggetVal_linear = np.exp(2*log_mean+log_var)*(np.exp(log_var)-1) # in linear space

            if self.do_mf:
                #results["valNugget"][self.g_name[ny]] = float(self.m_list[ny].gpy_model['Gaussian_noise.variance'])
                pass
            else:
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

        if self.do_simulation:
            results["predError"] = {}
            results["predError"]["percent"] = self.perc_thr.tolist()
            results["predError"]["value"] = self.perc_val.tolist()
            results["fem"] = {}
            try:
                results["fem"]["inputFile"] = self.inpFile
                results["fem"]["postprocessScript"] = self.postFile
                results["fem"]["program"] = self.appName
            except:
                results["fem"]["inputFile"] = 0
                results["fem"]["postprocessScript"] = 0
                results["fem"]["program"] = 0


        if self.do_sampling:
            if self.use_existing:
                results["inpData"] = self.inpData
                results["outData"] = self.outData
        else:
            results["inpData"] = self.inpData
            if not self.do_simulation:
                results["outData"] = self.outData

        if self.do_mf:
            if self.mf_case == 'data-model' or self.mf_case == 'data-data':
                results["inpData_HF"] = self.inpData_hf
                results["outData_HF"] = self.outData_hf
                results["valSamp_HF"] = self.X_hf.shape[0]

            elif self.mf_case == 'model-data':
                results["inpData_LF"] = self.inpData_lf
                results["outData_LF"] = self.outData_lf
                results["valSamp_LF"] = self.X_lf.shape[0]

            if self.hf_is_model and self.use_existing_hf:
                results["inpData_HF"] = self.inpData_hf
                results["outData_HF"] = self.outData_hf
                results["valSamp_HF"] = self.X_hf.shape[0]

            if self.lf_is_model and self.use_existing_lf:
                results["inpData_LF"] = self.inpData_lf
                results["outData_LF"] = self.outData_lf
                results["valSamp_LF"] = self.X_lf.shape[0]

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
            file.write("  - sampling : {}\n".format(self.do_sampling))
            file.write("  - simulation : {}\n".format(self.do_simulation))
            if self.do_doe:
                file.write("  - design of experiments : {} \n".format(self.do_doe))
            if not self.do_doe:
                if self.do_simulation and self.do_sampling:
                    file.write(
                        "  - design of experiments (DoE) turned off - DoE evaluation time exceeds the model simulation time \n")
            file.write('\n')

            file.write('* Convergence\n')
            file.write('  - exit code : "{}"\n'.format(self.exit_code))
            file.write('    simulation terminated as ')
            if self.exit_code == 'count':
                file.write('number of counts reached the maximum (max={})"\n'.format(self.thr_count))
            elif self.exit_code == 'accuracy':
                file.write('minimum accuracy level (NRMSE={:.2f}) is achieved"\n'.format(self.thr_NRMSE))
            elif self.exit_code == 'time':
                file.write('maximum running time (t={:.1f}s) reached"\n'.format(self.thr_t))
            else:
                file.write('cannot identify the exit code\n')
            file.write('  - number of simulations (count) : {}\n'.format(self.n_samp))
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

            file.close()

        print("Results Saved")
        return 0

    def weights_node2(self, node, nodes, ls):
        nodes = np.asarray(nodes)
        deltas = nodes - node

        deltas_norm = np.zeros(deltas.shape)
        for nx in range(ls.shape[0]):
            deltas_norm[:, nx] = (deltas[:, nx]) / ls[nx]  # additional weights?

        dist_ls = np.sqrt(np.sum(pow(deltas_norm, 2), axis=1))

        weig = np.exp(-pow(dist_ls,2))
        if (sum(weig)==0):
            weig = np.ones(nodes.shape[0])
        return weig/sum(weig)

def run_FEM(X, id_sim, rv_name, work_dir, workflowDriver, runIdx):
    # runIdx=0 : single model
    # runIdx=1 : HF
    # runIdx=2 : LF

    if runIdx == 0 :
        templatedirFolder = '/templatedir'
        workdirFolder = '/workdir.' + str(id_sim + 1)
    else:
        templatedirFolder = '/templatedir.' + str(runIdx)
        workdirFolder = '/workdir.' + str(runIdx) + '.' + str(id_sim + 1)

    X = np.atleast_2d(X)
    x_dim = X.shape[1]

    if X.shape[0] > 1:
        errlog = errorLog(work_dir)
        msg = 'do one simulation at a time'
        errlog.exit(msg)


    # (1) create "workdir.idx " folder :need C++17 to use the files system namespace
    current_dir_i = work_dir + workdirFolder

    print(id_sim)

    try:
        shutil.copytree(work_dir + templatedirFolder, current_dir_i)
    except Exception as ex:
        errlog = errorLog(work_dir)
        msg = 'Error running FEM: ' + str(ex)
        errlog.exit(msg)


    # (2) write param.in file
    outF = open(current_dir_i + '/params.in', 'w')

    outF.write('{}\n'.format(x_dim))
    for i in range(x_dim):
        outF.write('{} {}\n'.format(rv_name[i], X[0, i]))
    outF.close()

    # (3) run workflow_driver.bat
    os.chdir(current_dir_i)

    workflow_run_command = '{}/{}'.format(current_dir_i, workflowDriver)
    subprocess.check_call(workflow_run_command, shell=True)

    # (4) reading results
    if glob.glob('results.out'):
        g = np.loadtxt('results.out').flatten()
    else:
        errlog = errorLog(work_dir)
        msg = 'Error running FEM: results.out missing at ' + current_dir_i
        errlog.exit(msg)

    if g.shape[0]==0:
        errlog = errorLog(work_dir)
        msg = 'Error running FEM: results.out is empty'
        errlog.exit(msg)

    os.chdir("../")

    if np.isnan(np.sum(g)):
        errlog = errorLog(work_dir)
        msg = 'Error running FEM: Response value at workdir.{} is NaN'.format(id_sim+1)
        errlog.exit(msg)

    return g, id_sim


def run_FEM_batch(X,id_sim, rv_name, do_parallel, y_dim, os_type, run_type, pool, t_init, t_thr, runIdx):
    X = np.atleast_2d(X)
    # Windows
    if os_type.lower().startswith('win'):
        workflowDriver = "workflow_driver.bat"
    else:
        workflowDriver = "workflow_driver"

    nsamp = X.shape[0]
    if not do_parallel:
        Y = np.zeros((nsamp,y_dim))
        for ns in range(nsamp):
            Y[ns,:], id_sim_current = run_FEM(X[ns,:],id_sim+ns,rv_name, work_dir, workflowDriver, runIdx)
            if time.time() - t_init > t_thr:
                X = X[:ns, :]
                Y = Y[:ns, :]
                break               

        return X, Y, id_sim_current+1

    if do_parallel:
        print("Running {} simulations in parallel".format(nsamp))
        tmp = time.time()
        iterables = ((X[i, :][np.newaxis], id_sim + i, rv_name, work_dir, workflowDriver, runIdx) for i in range(nsamp))
        try:
            result_objs = list(pool.starmap(run_FEM, iterables))
            print("Simulation time = {} s".format(time.time() - tmp));  tmp = time.time();
        except KeyboardInterrupt:
            print("Ctrl+c received, terminating and joining pool.")
            try:
                pool.shutdown()
            except Exception:
                sys.exit()

        tmp = time.time();
        print("=====================================")
        Nsim = len(list((result_objs)))
        Y = np.zeros((Nsim, y_dim))

        for val, id in result_objs:
            if np.isnan(np.sum(val)):
                Nsim = id - id_sim
                X = X[:Nsim, :]
                Y = Y[:Nsim, :]
            else:
                Y[id - id_sim, :] = val

    return X, Y, id_sim + Nsim

def read_txt(text_dir, errlog):
    if not os.path.exists(text_dir):
        msg = "Error: file does not exist: " + text_dir
        errlog.exit(msg)

    with open(text_dir) as f:
        # Iterate through the file until the table starts
        header_count = 0
        for line in f:
            if line.startswith('%'):
                header_count = header_count + 1
                print(line)

    
        # X = np.loadtxt(f, skiprows=header_count, delimiter=',')
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
                    errlog.exit(msg)

    if X.ndim == 1:
        X = np.array([X]).transpose()

    return X

def closest_node(node, nodes, ll):

    nodes = np.asarray(nodes)
    deltas = nodes - node
    deltas_norm = np.zeros(deltas.shape)
    for nx in range(nodes.shape[1]):
        deltas_norm[:, nx] = deltas[:, nx] /  ll[nx]

    dist_2 = np.einsum('ij,ij->i', deltas_norm, deltas_norm) # square sum
    return np.argmin(dist_2)

def imse(m_tmp, xcandi, xq, phiqr, i):
    X = m_tmp.X
    Y = m_tmp.Y
    X_tmp = np.vstack([X, xcandi])
    Y_tmp = np.zeros((Y.shape[0] + 1, Y.shape[1]))  # any variables
    m_tmp.set_XY(X=X_tmp, Y=Y_tmp)
    dummy, Yq_var = m_tmp.predict(xq)
    IMSEc1 = 1 / xq.shape[0] * sum(phiqr.flatten() *Yq_var.flatten())
    
    return IMSEc1, i


# ==========================================================================================

class errorLog(object):

    def __init__(self, work_dir):
        self.file = open('{}/dakota.err'.format(work_dir), "w")

    def exit(self, msg):
        print(msg)
        self.file.write(msg)
        self.file.close()
        exit(-1)

    def terminate(self):
        self.file.close()

def build_surrogate(work_dir, os_type, run_type):
    # t_total = time.process_time()
    filename = 'SimGpModel'

    f = open(work_dir + '/templatedir/dakota.json')
    try:
        inp = json.load(f)
    except ValueError:
        msg = 'invalid json format - dakota.json'
        errlog.exit(msg)

    f.close()

    if inp['UQ_Method']['uqType'] != 'Train GP Surrogate Model':
        msg = 'UQ type inconsistency : user wanted <' + inp['UQ_Method'][
            'uqType'] + '> but called <Global Surrogate Modeling> program'
        errlog.exit(msg)


    gp = GpFromModel(work_dir, run_type, os_type, inp, errlog)
    gp.save_model(filename)
    gp.term()

# the actual execution

# ==========================================================================================

# the actual execution

if __name__ == "__main__":
    inputArgs = sys.argv
    work_dir = inputArgs[1].replace(os.sep, '/')
    run_type = inputArgs[3]
    os_type = inputArgs[2]

    errlog = errorLog(work_dir)
    if error_tag==True:
        if os_type.lower().startswith('win'):
            msg = 'Failed to load python module [' + moduleName + ']. Go to [File-Preference-Python] and reset the path.'
        else:
            msg = 'Failed to load python module [' + moduleName + ']. Did you forget <pip3 install nheri_simcenter --upgrade>?'
        errlog.exit(msg)

    result_file = "results.out"
    #sys.exit(build_surrogate(work_dir, os_type, run_type))    
    build_surrogate(work_dir, os_type, run_type)
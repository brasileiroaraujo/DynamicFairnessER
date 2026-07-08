import numpy as np
import effector
import time



def generate_dataset_uncorrelated(N):
    x1 = np.random.uniform(-1, 1, size=N)
    x2 = np.random.uniform(-1, 1, size=N)
    x3 = np.random.uniform(-1, 1, size=N)
    return np.stack((x1, x2, x3), axis=-1)

def generate_dataset_correlated(N):
    x1 = np.random.uniform(-1, 1, size=N)
    x2 = np.random.uniform(-1, 1, size=N)
    x3 = x1
    return np.stack((x1, x2, x3), axis=-1)

# generate the dataset for the uncorrelated and correlated setting
N = 10_000
X_uncor = generate_dataset_uncorrelated(N)
X_cor = generate_dataset_correlated(N)

def model(x):
    f = np.where(x[:,2] > 0, 3*x[:,0] + x[:,2], -3*x[:,0] + x[:,2])
    return f

def model_jac(x):
    dy_dx = np.zeros_like(x)

    ind1 = x[:, 2] > 0
    ind2 = x[:, 2] <= 0

    dy_dx[ind1, 0] = 3
    dy_dx[ind2, 0] = -3
    dy_dx[:, 2] = 1
    return dy_dx

# def model_jac(x):
#     dy_dx = np.zeros_like(x)
#
#     ind1 = x[:, 2] > 0
#     ind2 = x[:, 2] <= 0
#
#     dy_dx[ind1, 0] = 3
#     dy_dx[ind2, 0] = -3
#     dy_dx[:, 2] = 1
#     return dy_dx
#
# Y_cor = model(X_cor)
# Y_uncor = model(X_uncor)


#Regional
# regional_pdp = effector.PDP(data=X_cor, model=model, feature_names=['x1','x2','x3'], axis_limits=np.array([[-1,1],[-1,1],[-1,1]]).T)
# regional_pdp.fit(features="all", nof_candidate_splits_for_numerical=11, centering=True)

regional_pdp = effector.RegionalPDP(data=X_uncor, model=model, feature_names=['x1','x2','x3'], axis_limits=np.array([[-1,1],[-1,1],[-1,1]]).T)
regional_pdp.fit(features="all", heter_pcg_drop_thres=0.3, nof_candidate_splits_for_numerical=11, centering=True)

regional_pdp.show_partitioning(features=0)
print('===================================')
regional_pdp.show_partitioning(features=1)
print('===================================')
regional_pdp.show_partitioning(features=2)
print('===================================')





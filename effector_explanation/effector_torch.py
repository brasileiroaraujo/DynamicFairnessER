import effector
import torch
import torch.nn as nn
import numpy as np

# X = ... # input data
# y = ... # target data

class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.fc1 = nn.Linear(3, 10) #3 number of features (dimension)
        self.fc2 = nn.Linear(10, 1)

    def forward(self, x):
        x = self.fc1(x)
        x = self.fc2(x)
        return x

model = Net()


def generate_dataset_uncorrelated(N):
    x1 = np.random.uniform(-1, 1, size=N)
    x2 = np.random.uniform(-1, 1, size=N)
    x3 = np.random.uniform(-1, 1, size=N)
    return np.stack((x1, x2, x3), axis=-1)

def model_uncorrelated(x):
    f = np.where(x[:,2] > 0, 3*x[:,0] + x[:,2], -3*x[:,0] + x[:,2])
    return f

N = 10
X = generate_dataset_uncorrelated(N)
y = model_uncorrelated(X)

# train model
# optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
# criterion = nn.MSELoss()
# for epoch in range(10):
#     optimizer.zero_grad()
#     y_pred = model(X)
#     loss = criterion(y_pred, y)
#     loss.backward()
#     optimizer.step()

def model_callable(X):
    return model(torch.tensor(X, dtype=torch.float32)).detach().numpy()

def model_jac_callable(X):
    X = torch.tensor(X, dtype=torch.float32)
    X.requires_grad = True
    y = model(X)
    return torch.autograd.grad(y, X)[0].numpy()


# global and regional pdp effect
# effector.PDP(X, model_callable).plot(feature=0)
print(type(X))
effector.RegionalPDP(X, model_callable).show_partitioning(features=0) #.plot(feature=0, node_idx=0)

# global and regional rhale effect
# effector.RHALE(X, model_callable, model_jac_callable).plot(feature=0)
# effector.RegionalRHALE(X, model_callable, model_jac_callable).plot(feature=0, node_idx=0)
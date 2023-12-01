import torch
import torch.nn as nn
from sklearn.base import BaseEstimator
from tqdm.auto import tqdm
import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.utils.validation import check_X_y, check_array, check_is_fitted
from torch.utils.data import TensorDataset
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

class DynamicANN(nn.Module):
    def __init__(self, input_dim, layers, activations, dropout):
        super(DynamicANN, self).__init__()
        self.layers = nn.ModuleList()
        self.activations = activations
        self.dropout = nn.Dropout(dropout)

        for i in range(len(layers)):
            if i == 0:
                self.layers.append(nn.Linear(input_dim, layers[i]))
            else:
                self.layers.append(nn.Linear(layers[i-1], layers[i]))

    def forward(self, x):
        for i, layer in enumerate(self.layers):
            x = layer(x)

            # if i < len(self.activations):
            #     if self.activations[i] == 'relu':
            #         x = nn.functional.relu(x)
            #     elif self.activations[i] == 'sigmoid':
            #         x = nn.functional.sigmoid(x)
            #             activation = self.activations[i]
            # # 모든 활성화 함수 사용가능하게끔 추가
            if i < len(self.activations):
                activation = self.activations[i]
                if activation == 'relu':
                    x = nn.functional.relu(x)
                elif activation == 'sigmoid':
                    x = nn.functional.sigmoid(x)
                elif activation == 'tanh':
                    x = nn.functional.tanh(x)
                elif activation == 'softmax':
                    x = nn.functional.softmax(x, dim=1)
                elif activation == 'leaky_relu':
                    x = nn.functional.leaky_relu(x)
                elif activation == 'elu':
                    x = nn.functional.elu(x)
                elif activation == 'selu':
                    x = nn.functional.selu(x)
                elif activation == 'gelu':
                    x = nn.functional.gelu(x)
                elif activation == 'p_relu':
                    x = nn.functional.prelu(x)
                elif activation == 'softplus':
                    x = nn.functional.softplus(x)
                elif activation == 'softsign':
                    x = nn.functional.softsign(x)
                elif activation == 'softmin':
                    x = nn.functional.softmin(x)
            # x = self.dropout(x)
        return x

class DynamicANNWrapper(BaseEstimator, RegressorMixin):
    def __init__(self, input_dim, layers, activations, dropout, epochs=10 ,  batch_size=32 , criterion="nn.CrossEntropyLoss()" , lr=0.001):
        self.input_dim = input_dim
        self.layers = layers
        self.activations = activations
        self.dropout = dropout
        self.epochs = epochs
        self.model = DynamicANN(input_dim, layers, activations, dropout)
        
        #gpu사용위해 추가된 부분
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu") # device 설정
        self.model = self.model.to(self.device) # 모델을 device에 올림
        #gpu사용위해 추가된 부분

        self.batch_size = batch_size  
        self.criterion = criterion
        self.lr = lr

    def fit(self, X, y):
        X, y = check_X_y(X, y, dtype='float32')
        input_dim = X.shape[1]
        assert input_dim == self.input_dim, "Input dimension mismatch"

        X_tensor = torch.tensor(X)

        #gpu사용위해 추가된 부분
        X_tensor = X_tensor.to(self.device) # 데이터를 device에 올림
        #gpu사용위해 추가된 부분

        # y_tensor = torch.tensor(y, dtype=torch.float32).view(-1, 1)
        # y_tensor = torch.tensor(y, dtype=torch.long).view(-1, 1)
        y_tensor = torch.tensor(y, dtype=torch.long)

        # 여기서 주목해야 할 부분은 dtype=torch.float32입니다. 다중 클래스 분류 문제의 경우 CrossEntropyLoss를 사용하므로 y가 정수형이어야 합니다.
        # 따라서 dtype=torch.long으로 변경해야 합니다

        # criterion = nn.MSELoss()
        # criterion = nn.CrossEntropyLoss()
        criterion = eval(self.criterion)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        
        train_dataset = TensorDataset(X_tensor, y_tensor)
        train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)

        for epoch in tqdm(range(self.epochs)):
            self.model.train()

            total_loss = 0.0

            for batch_data, batch_target in (train_loader):

                #gpu사용위해 추가된 부분
                batch_data, batch_target = batch_data.to(self.device), batch_target.to(self.device) # 데이터를 device에 올림
                #gpu사용위해 추가된 부분

                optimizer.zero_grad()
                outputs = self.model(batch_data)
                loss = criterion(outputs, batch_target)
                loss.backward()
                optimizer.step()

                total_loss += loss.item()

            average_loss = total_loss / len(train_loader)
            print(f'Epoch {epoch + 1}/{self.epochs}, Average Training Loss: {average_loss:.4f}')

        self.is_fitted_= True 
    
    def predict(self, X):
        check_is_fitted(self)
        ##
        X = check_array(X, dtype='float32', force_all_finite=False)

        X_tensor = torch.tensor(X)

        
        self.model.eval()
        with torch.no_grad():
            #predictions = self.model(X_tensor).numpy()
            #gpu사용위해 생략

            #gpu사용위해 추가된 부분
            predictions = self.model(X_tensor).cpu().numpy() #예측결과 cpu로 가져옴
            #gpu사용위해 추가된 부분 

        ######### 여기가 원래 없는 코드인데 이거 numpy배열에서 확률로 설정된 float값을 리턴한다. 그래서 우리가 원하는 클래스 값으로 변환해야함
        predictions = np.argmax(predictions, axis=1) #이거 리턴값 예측값을 찍어보면 확률로 나옴
        ########이 부분이 핵심임 다른 모델 만들때는 다르게 리턴해줘야함
        return predictions
    
    def score(self, X, y):

        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_true = torch.tensor(y, dtype=torch.float32).view(-1,1)

        self.model.eval()

        with torch.no_grad():
            y_prd = self.model(X_tensor).argmax(dim=1).numpy()
        
        y_prd = self.predict(X_tensor)
        
        return accuracy_score(y_true , y_prd)

import torch
import torch.nn as nn
import numpy as np
from sklearn.preprocessing import OneHotEncoder
import re

# Função para ler o arquivo .txt e extrair os títulos
def extract_titles_from_txt(file_path):
    titles = []
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines:
            # Usar regex para capturar o valor após "COL title VAL"
            match = re.search(r'COL title VAL (.*?) COL', line)
            if match:
                title = match.group(1).strip()
                titles.append(title)
                # print((title))
    return titles, lines

# Função para concatenar novas strings com o dataset original
def concatenate_synthetic_with_original(synthetic_titles, original_lines, file_path):
    with open(file_path, 'a') as file:
        for title in synthetic_titles:
            # Gerar uma nova linha no mesmo formato original, substituindo apenas o título
            new_line = f"COL title VAL {title} COL manufacturer VAL synthetic COL price VAL 0\n"
            file.write(new_line)

# Converter strings em one-hot encoding
def string_to_onehot(strings):
    chars = sorted(list(set("".join(strings))))
    enc = OneHotEncoder(handle_unknown='ignore', sparse=False)
    enc.fit(np.array(chars).reshape(-1, 1))
    onehot_encoded = [enc.transform(np.array(list(s)).reshape(-1, 1)) for s in strings]
    return onehot_encoded, enc

# Função para gerar um vetor de ruído aleatório para o gerador
def generate_noise(batch_size, latent_dim):
    return torch.randn(batch_size, latent_dim)

# Definir o Gerador (Generator) e Discriminador (Discriminator)
class Generator(nn.Module):
    def __init__(self, latent_dim, output_size):
        super(Generator, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(latent_dim, 256),
            nn.LeakyReLU(0.2),
            nn.Linear(256, 512),
            nn.LeakyReLU(0.2),
            nn.Linear(512, output_size),
            nn.Tanh()  # Change to Tanh for more output variation
        )

    def forward(self, z):
        return self.model(z)

class Discriminator(nn.Module):
    def __init__(self, input_size):
        super(Discriminator, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(input_size, 512),
            nn.LeakyReLU(0.2),
            nn.Linear(512, 256),
            nn.LeakyReLU(0.2),
            nn.Linear(256, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.model(x)

# Função para converter one-hot de volta para string
def onehot_to_string(onehot_encoded, encoder):
    chars = encoder.categories_[0]
    idx = np.argmax(onehot_encoded, axis=1)
    return "".join(chars[idx])

# Função de treinamento básico do GAN
def train_gan(real_data, generator, discriminator, latent_dim, epochs=2000, batch_size=5):  # Increased epochs for better training
    loss_function = nn.BCELoss()
    optimizer_g = torch.optim.Adam(generator.parameters(), lr=0.0001)  # Adjusted learning rate for stability
    optimizer_d = torch.optim.Adam(discriminator.parameters(), lr=0.0001)

    real_data = torch.tensor(real_data, dtype=torch.float32)

    for epoch in range(epochs):
        for _ in range(batch_size):
            noise = generate_noise(batch_size, latent_dim)
            generated_data = generator(noise)

            real_labels = torch.ones(batch_size, 1)
            fake_labels = torch.zeros(batch_size, 1)

            predictions_real = discriminator(real_data[:batch_size].view(batch_size, -1))
            predictions_fake = discriminator(generated_data.detach())

            loss_d_real = loss_function(predictions_real, real_labels)
            loss_d_fake = loss_function(predictions_fake, fake_labels)
            loss_d = (loss_d_real + loss_d_fake) / 2

            optimizer_d.zero_grad()
            loss_d.backward()
            optimizer_d.step()

        noise = generate_noise(batch_size, latent_dim)
        generated_data = generator(noise)
        predictions = discriminator(generated_data)

        loss_g = loss_function(predictions, real_labels)

        optimizer_g.zero_grad()
        loss_g.backward()
        optimizer_g.step()

        if epoch % 500 == 0:  # Print progress every 500 epochs
            print(f"Epoch {epoch}, Loss D: {loss_d.item()}, Loss G: {loss_g.item()}")

# Função principal para gerar strings sintéticas a partir de títulos extraídos
def generate_synthetic_titles(file_path, num_synthetic_titles, output_file):
    titles, original_lines = extract_titles_from_txt(file_path)

    # Preparar os dados de treinamento para o GAN
    onehot_data, encoder = string_to_onehot(titles)
    max_len = max([len(s) for s in onehot_data])

    # Padding para strings mais curtas
    padded_data = [np.pad(s, ((0, max_len - len(s)), (0, 0)), 'constant') for s in onehot_data]

    # Instanciar o Gerador e o Discriminador
    latent_dim = 10
    output_size = max_len * len(encoder.categories_[0])

    generator = Generator(latent_dim, output_size)
    discriminator = Discriminator(output_size)

    # Treinar o GAN
    train_gan(padded_data, generator, discriminator, latent_dim, epochs=200, batch_size=5)  # Increased epochs

    # Gerar novas strings sintéticas
    noise = generate_noise(num_synthetic_titles, latent_dim)
    synthetic_data = generator(noise).detach().numpy()

    # Converter as strings one-hot geradas de volta para strings reais
    synthetic_titles = []
    for i in range(num_synthetic_titles):
        synthetic_title = onehot_to_string(synthetic_data[i].reshape(max_len, -1), encoder)
        print(synthetic_title)
        synthetic_titles.append(synthetic_title)

    # Concatenar com os dados originais e gravar no arquivo de saída
    concatenate_synthetic_with_original(synthetic_titles, original_lines, output_file)


input_file = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/Walmart-Amazon/test.txt"
output_file = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/Walmart-Amazon/test_synt.txt"


# Gerar títulos sintéticos e adicionar ao arquivo
generate_synthetic_titles(input_file, num_synthetic_titles=10, output_file=output_file)

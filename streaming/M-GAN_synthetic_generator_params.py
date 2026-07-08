import torch
import torch.nn as nn
import numpy as np
from sklearn.preprocessing import OneHotEncoder
import re
import random

# Função para ler o arquivo .txt e extrair os títulos
def extract_titles_from_txt(file_path):
    titles = []
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines:
            match = re.search(r'COL title VAL (.*?) COL', line)
            if match:
                title = match.group(1).strip()
                titles.append(title)
    return titles, lines

# Função para concatenar novas strings com o dataset original
def concatenate_synthetic_with_original(synthetic_titles, original_lines, file_path, increasing_factor):
    with open(file_path, 'a', encoding='utf-8') as file:
        # for title in synthetic_titles:
        #     new_line = f"COL title VAL {title} COL manufacturer VAL synthetic COL price VAL 0.0\n"
        #     file.write(new_line)
        print("Number of synthetic_titles: " + str(len(synthetic_titles)))
        for i in range(increasing_factor):
            for line in original_lines:
                title = random.choice(synthetic_titles)
                new_line = f"COL title VAL {title} COL manufacturer VAL synthetic COL price VAL 0.0\t"
                triple = line.split("\t")
                if (int(triple[2].strip()) == 1): #Maintain the matches
                    file.write(line)
                else:
                    file.write(new_line + triple[1]+"\t" + triple[2])


# Converter palavras (tokens) em one-hot encoding
def string_to_onehot_token(strings):
    tokens = sorted(list(set(" ".join(strings).split())))  # Separar palavras (tokens)
    enc = OneHotEncoder(handle_unknown='ignore', sparse=False)
    enc.fit(np.array(tokens).reshape(-1, 1))

    # Codificar cada título como uma sequência de tokens (palavras)
    onehot_encoded = [enc.transform(np.array(s.split()).reshape(-1, 1)) for s in strings]
    return onehot_encoded, enc

# Função para gerar um vetor de ruído aleatório para o gerador
def generate_noise(batch_size, latent_dim, noise_factor=1.0):
    noise = torch.randn(batch_size, latent_dim)
    noise = noise * noise_factor  # Controla a intensidade do ruído
    return noise

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
            nn.Tanh()  # Tanh para limitar a saída
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

# Função para converter one-hot de volta para string (tokens)
def onehot_to_string_token(onehot_encoded, encoder):
    tokens = encoder.categories_[0]
    idx = np.argmax(onehot_encoded, axis=1)
    return " ".join(tokens[idx])

# Função de treinamento básico do GAN
def train_gan(real_data, generator, discriminator, latent_dim, epochs=1000, batch_size=5):
    loss_function = nn.BCELoss()
    optimizer_g = torch.optim.Adam(generator.parameters(), lr=0.0001)
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

        if epoch % 500 == 0:
            print(f"Epoch {epoch}, Loss D: {loss_d.item()}, Loss G: {loss_g.item()}")


def random_variation(variation):
    words = variation.split()
    num_words_selected = random.randint(1, min(4, len(words)))
    selected_words = random.sample(words, num_words_selected)

    return " ".join(selected_words)

# Função para modificar palavras específicas com variações geradas pelo GAN
def generate_variation(generator, encoder, max_len, latent_dim):
    # Gerar ruído para o GAN
    noise = generate_noise(1, latent_dim)
    # Gerar a variação
    synthetic_data = generator(noise).detach().numpy()
    # Converter o dado gerado para tokens
    variation = onehot_to_string_token(synthetic_data.reshape(max_len, -1), encoder)

    return random_variation(variation)

# Função para alterar algumas palavras com o GAN
def modify_title_with_gan(title, generator, encoder, max_len, latent_dim, words_to_modify):
    title_words = title.split()
    for idx in words_to_modify:
        # Substituir a palavra por uma variação gerada pelo GAN
        title_words[idx] = generate_variation(generator, encoder, max_len, latent_dim)
    return " ".join(title_words)

# Função principal para gerar strings sintéticas mantendo palavras-chave e usando o GAN para variações
def generate_synthetic_titles_with_gan(file_path, output_file, latent_dim=10, increasing_factor=1):
    titles, original_lines = extract_titles_from_txt(file_path)

    # Preparar os dados de treinamento para o GAN em nível de tokens (palavras)
    onehot_data, encoder = string_to_onehot_token(titles)
    max_len = max([len(s) for s in onehot_data])

    # Padding para strings mais curtas
    padded_data = [np.pad(s, ((0, max_len - len(s)), (0, 0)), 'constant') for s in onehot_data]

    # Instanciar o Gerador e o Discriminador
    output_size = max_len * len(encoder.categories_[0])

    generator = Generator(latent_dim, output_size)
    discriminator = Discriminator(output_size)

    # Treinar o GAN
    train_gan(padded_data, generator, discriminator, latent_dim, epochs=20, batch_size=5)

    # Gerar novas variações parciais com o GAN
    synthetic_titles = []
    for title in titles:
        # Selecionar aleatoriamente 1 ou 2 palavras para serem modificadas
        num_words_to_modify = random.randint(1, 2)
        if len(title.split()) == 1:
            num_words_to_modify = 1
        words_to_modify = random.sample(range(len(title.split())), num_words_to_modify)

        # Modificar o título gerando variações com o GAN
        modified_title = modify_title_with_gan(title, generator, encoder, max_len, latent_dim, words_to_modify)
        synthetic_titles.append(modified_title)

    # Concatenar com os dados originais e gravar no arquivo de saída
    concatenate_synthetic_with_original(synthetic_titles, original_lines, output_file, increasing_factor)


input_file = "input_path"
output_file = "output_path"

# Generate synthetic titles by retaining part of the original titles and using the GAN for variations.
generate_synthetic_titles_with_gan(input_file, output_file=output_file, latent_dim=5,  increasing_factor = 100)


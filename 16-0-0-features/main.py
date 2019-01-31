'''
# data
- glove, fasttext, paragram
- features: capitals/length, words/uniques
# model
- RNN, Attention, Capsule
# train
- 5 SKF
- unfreeze embedding layer
'''
from datetime import datetime; start = datetime.now()
from logging import getLogger, FileHandler, StreamHandler, Formatter, DEBUG, INFO
import gc, os, random, re
from time import time; start_time = time()

import numpy as np
import pandas as pd
from sklearn import metrics
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from tqdm import tqdm

from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences

import torch
from torch import nn, optim
from torch.nn import functional as F
from torch.utils.data import TensorDataset, DataLoader, Dataset


# parameters
debug = False
one_epoch = False
# model
emb_size = 300
max_features = 120000
maxlen = 70
embedding_trainable = False
n_capsule = 5
capsule_dim = 5
# data
test_size = 0.1
random_state = 2018
batch_size = 512
batch_size_val = 4096
# training
device = 'cuda:0'
thresholds = np.arange(0.3, 0.501, 0.01)
n_splits = 5
lr = 0.001
epochs = 5
early_stopping = False
min_delta = 0.
patience = 5
epoch_unfreeze = 2

seed = 2018
os.environ['PYTHONHASHSEED'] = str(seed)
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed(seed)
torch.backends.cudnn.deterministic = True

emb_paths = {
    'glove': '../input/embeddings/glove.840B.300d/glove.840B.300d.txt',
    'fasttext': '../input/embeddings/wiki-news-300d-1M/wiki-news-300d-1M.vec',
    'paragram': '../input/embeddings/paragram_300_sl999/paragram_300_sl999.txt',
    # 'google': '../input/embeddings/GoogleNews-vectors-negative300/GoogleNews-vectors-negative300.bin'
}
# https://www.kaggle.com/theoviel/improve-your-score-with-text-preprocessing-v2
contraction_mapping = {"ain't": "is not", "aren't": "are not","can't": "cannot", "'cause": "because", "could've": "could have", "couldn't": "could not", "didn't": "did not",  "doesn't": "does not", "don't": "do not", "hadn't": "had not", "hasn't": "has not", "haven't": "have not", "he'd": "he would","he'll": "he will", "he's": "he is", "how'd": "how did", "how'd'y": "how do you", "how'll": "how will", "how's": "how is",  "I'd": "I would", "I'd've": "I would have", "I'll": "I will", "I'll've": "I will have","I'm": "I am", "I've": "I have", "i'd": "i would", "i'd've": "i would have", "i'll": "i will",  "i'll've": "i will have","i'm": "i am", "i've": "i have", "isn't": "is not", "it'd": "it would", "it'd've": "it would have", "it'll": "it will", "it'll've": "it will have","it's": "it is", "let's": "let us", "ma'am": "madam", "mayn't": "may not", "might've": "might have","mightn't": "might not","mightn't've": "might not have", "must've": "must have", "mustn't": "must not", "mustn't've": "must not have", "needn't": "need not", "needn't've": "need not have","o'clock": "of the clock", "oughtn't": "ought not", "oughtn't've": "ought not have", "shan't": "shall not", "sha'n't": "shall not", "shan't've": "shall not have", "she'd": "she would", "she'd've": "she would have", "she'll": "she will", "she'll've": "she will have", "she's": "she is", "should've": "should have", "shouldn't": "should not", "shouldn't've": "should not have", "so've": "so have","so's": "so as", "this's": "this is","that'd": "that would", "that'd've": "that would have", "that's": "that is", "there'd": "there would", "there'd've": "there would have", "there's": "there is", "here's": "here is","they'd": "they would", "they'd've": "they would have", "they'll": "they will", "they'll've": "they will have", "they're": "they are", "they've": "they have", "to've": "to have", "wasn't": "was not", "we'd": "we would", "we'd've": "we would have", "we'll": "we will", "we'll've": "we will have", "we're": "we are", "we've": "we have", "weren't": "were not", "what'll": "what will", "what'll've": "what will have", "what're": "what are",  "what's": "what is", "what've": "what have", "when's": "when is", "when've": "when have", "where'd": "where did", "where's": "where is", "where've": "where have", "who'll": "who will", "who'll've": "who will have", "who's": "who is", "who've": "who have", "why's": "why is", "why've": "why have", "will've": "will have", "won't": "will not", "won't've": "will not have", "would've": "would have", "wouldn't": "would not", "wouldn't've": "would not have", "y'all": "you all", "y'all'd": "you all would","y'all'd've": "you all would have","y'all're": "you all are","y'all've": "you all have","you'd": "you would", "you'd've": "you would have", "you'll": "you will", "you'll've": "you will have", "you're": "you are", "you've": "you have" }
punctuation = "/-'?!.,#$%\'()*+-/:;<=>@[\\]^_`{|}~" + '""“”’' + '∞θ÷α•à−β∅³π‘₹´°£€\×™√²—–&'
punctuation_mapping = {"‘": "'", "₹": "e", "´": "'", "°": "", "€": "e", "™": "tm", "√": " sqrt ", "×": "x", "²": "2", "—": "-", "–": "-", "’": "'", "_": "-", "`": "'", '“': '"', '”': '"', '“': '"', "£": "e", '∞': 'infinity', 'θ': 'theta', '÷': '/', 'α': 'alpha', '•': '.', 'à': 'a', '−': '-', 'β': 'beta', '∅': '', '³': '3', 'π': 'pi', }
misspell_dict = {'colour': 'color', 'centre': 'center', 'favourite': 'favorite', 'travelling': 'traveling', 'counselling': 'counseling', 'theatre': 'theater', 'cancelled': 'canceled', 'labour': 'labor', 'organisation': 'organization', 'wwii': 'world war 2', 'citicise': 'criticize', 'youtu ': 'youtube ', 'Qoura': 'Quora', 'sallary': 'salary', 'Whta': 'What', 'narcisist': 'narcissist', 'howdo': 'how do', 'whatare': 'what are', 'howcan': 'how can', 'howmuch': 'how much', 'howmany': 'how many', 'whydo': 'why do', 'doI': 'do I', 'theBest': 'the best', 'howdoes': 'how does', 'mastrubation': 'masturbation', 'mastrubate': 'masturbate', "mastrubating": 'masturbating', 'pennis': 'penis', 'Etherium': 'Ethereum', 'narcissit': 'narcissist', 'bigdata': 'big data', '2k17': '2017', '2k18': '2018', 'qouta': 'quota', 'exboyfriend': 'ex boyfriend', 'airhostess': 'air hostess', "whst": 'what', 'watsapp': 'whatsapp', 'demonitisation': 'demonetization', 'demonitization': 'demonetization', 'demonetisation': 'demonetization', 'pokémon': 'pokemon'}

# logger
log_file = 'log.txt'
if os.path.exists(log_file): os.remove(log_file)  # noqa
fh = FileHandler(log_file)
fh.setLevel(DEBUG)
sh = StreamHandler()
sh.setLevel(INFO)
for handler in [fh, sh]:
    formatter = Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)
logger = getLogger(__name__)
logger.setLevel(INFO)
logger.addHandler(fh)
logger.addHandler(sh)


class Attention(nn.Module):
    def __init__(self, hidden_size, step_size, bias=True, **kwargs):
        super(Attention, self).__init__()

        self.hidden_size = hidden_size
        self.step_size = step_size

        weight = torch.zeros(hidden_size, 1)
        nn.init.xavier_uniform_(weight)
        self.weight = nn.Parameter(weight)
        self.bias = nn.Parameter(torch.zeros(step_size)) if bias else None

    def forward(self, x, mask=None):
        eij = torch.mm(x.contiguous().view(-1, self.hidden_size), self.weight).view(-1, self.step_size)
        if self.bias is not None:
            eij += self.bias
        eij = torch.tanh(eij)
        a = torch.exp(eij)
        if mask is not None:
            a = a * mask
        a = a / torch.sum(a, dim=1, keepdim=True) + 1e-10
        weighted = x * torch.unsqueeze(a, -1)
        return torch.sum(weighted, dim=1)


class Capsule(nn.Module):
    def __init__(
        self, input_dim_capsule=64 * 2,
        num_capsule=n_capsule, dim_capsule=capsule_dim,
        routings=4, kernel_size=(9, 1), share_weights=True, activation='default',
        **kwargs
    ):
        super(Capsule, self).__init__(**kwargs)

        self.T_epsilon = 1e-7
        self.num_capsule = num_capsule
        self.dim_capsule = dim_capsule
        self.routings = routings
        self.kernel_size = kernel_size
        self.share_weights = share_weights
        if activation == 'default':
            self.activation = self.squash
        else:
            self.activation = nn.ReLU(inplace=True)

        if self.share_weights:
            self.W = nn.Parameter(
                nn.init.xavier_normal_(
                    torch.empty(1, input_dim_capsule, self.num_capsule * self.dim_capsule)))
        else:
            self.W = nn.Parameter(
                torch.randn(BATCH_SIZE, input_dim_capsule, self.num_capsule * self.dim_capsule))

    def forward(self, x):
        if self.share_weights:
            u_hat_vecs = torch.matmul(x, self.W)
        else:
            print('add later')

        batch_size = x.size(0)
        input_num_capsule = x.size(1)
        u_hat_vecs = u_hat_vecs.view(
            (batch_size, input_num_capsule, self.num_capsule, self.dim_capsule))
        u_hat_vecs = u_hat_vecs.permute(0, 2, 1, 3)
        # (batch_size,num_capsule,input_num_capsule)
        b = torch.zeros_like(u_hat_vecs[:, :, :, 0])

        for i in range(self.routings):
            b = b.permute(0, 2, 1)
            c = F.softmax(b, dim=2)
            c = c.permute(0, 2, 1)
            b = b.permute(0, 2, 1)
            # batch matrix multiplication
            outputs = self.activation(torch.einsum('bij,bijk->bik', (c, u_hat_vecs)))
            # outputs shape (batch_size, num_capsule, dim_capsule)
            if i < self.routings - 1:
                b = torch.einsum('bik,bijk->bij', (outputs, u_hat_vecs))
                # batch matrix multiplication
        return outputs  # (batch_size, num_capsule, dim_capsule)

    def squash(self, x, axis=-1):
        '''# text version of squash, slight different from original one.'''
        s_squared_norm = (x ** 2).sum(axis, keepdim=True)
        scale = torch.sqrt(s_squared_norm + self.T_epsilon)
        return x / scale


class RNN(nn.Module):

    def __init__(
        self, vocab_size, embedding_dim=300, embedding=None, embedding_trainable=False,
        hidden_dim=64, n_layers=1, device='cuda:0'
    ):
        super(RNN, self).__init__()
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        self.device = device

        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        if embedding is not None:
            self.embedding.weight = nn.Parameter(torch.tensor(embedding, dtype=torch.float32))
            self.embedding.weight.requires_grad = embedding_trainable
        # TODO: SpatialDropout1D
        self.dropout1 = nn.Dropout(0.5)
        self.lstm = nn.LSTM(
            embedding_dim, hidden_dim, num_layers=n_layers, bias=False, batch_first=True, dropout=0.,
            bidirectional=True)
        self.gru = nn.GRU(
            hidden_dim * 2, hidden_dim, num_layers=n_layers, bias=False, batch_first=True, dropout=0.,
            bidirectional=True)
        # self.attn_gru = Attention(hidden_dim * 2, maxlen)
        self.fc1 = nn.Linear(hidden_dim * 2, 16)
        self.bn = nn.BatchNorm1d(16)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(16, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        bs = x.size(0)
        h0 = torch.zeros(self.n_layers * 2, bs, self.hidden_dim).to(self.device)
        c0 = torch.zeros(self.n_layers * 2, bs, self.hidden_dim).to(self.device)

        x = self.embedding(x)
        x = self.dropout1(x)
        x, (h, c) = self.lstm(x, (h0, c0))
        x, hidden = self.gru(x, h)
        # x = self.attn_gru(x)
        x = x[:, -1, :]
        x = x.view(bs, -1)
        x = self.relu(self.bn(self.fc1(x)))
        x = self.sigmoid(self.fc2(x))

        return x.squeeze()


class RNNCapsule(nn.Module):
    def __init__(
        self, vocab_size, embedding_dim=300, embedding=None, embedding_trainable=False,
        hidden_size=64, n_layers=1, device='cuda:0'
    ):
        super(RNNCapsule, self).__init__()

        n_features = 2

        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        if embedding is not None:
            self.embedding.weight = nn.Parameter(torch.tensor(embedding, dtype=torch.float32))
            self.embedding.weight.requires_grad = embedding_trainable
        self.dropout_emb = nn.Dropout2d(0.1)

        self.lstm = nn.LSTM(embedding_dim, hidden_size, bidirectional=True, batch_first=True)
        self.gru = nn.GRU(hidden_size * 2, hidden_size, bidirectional=True, batch_first=True)
        self.lstm2 = nn.LSTM(hidden_size * 2, hidden_size, bidirectional=True, batch_first=True)

        self.attn_lstm = Attention(hidden_size * 2, maxlen)
        self.attn_gru = Attention(hidden_size * 2, maxlen)

        self.bn = nn.BatchNorm1d(16, momentum=0.5)
        self.fc1 = nn.Linear(hidden_size * 8 + 1 + n_features, 16)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.1)
        self.out = nn.Linear(16, 1)

        self.capsule = Capsule()
        self.linear_capsule = nn.Linear(n_capsule * capsule_dim, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x, features = x[0], x[1]
        h = self.embedding(x)
        h = self.dropout_emb(h)
        h_lstm, _ = self.lstm(h)
        h_gru, _ = self.gru(h_lstm)
        # capsule layer
        content3 = self.capsule(h_gru)
        content3 = self.dropout(content3)
        batch_size = content3.size(0)
        content3 = content3.view(batch_size, -1)
        content3 = self.relu(self.linear_capsule(content3))
        # attention
        attn_lstm = self.attn_lstm(h_lstm)
        attn_gru = self.attn_gru(h_gru)

        avg_pool = torch.mean(h_gru, 1)
        max_pool, _ = torch.max(h_gru, 1)

        out = torch.cat(
            [attn_lstm, attn_gru, content3, avg_pool, max_pool, features],
            1)
        out = self.relu(self.bn(self.fc1(out)))
        out = self.out(out)
        out = self.sigmoid(out)
        return out.squeeze()


class EarlyStopping(object):
    '''
    cf. https://gist.github.com/stefanonardo/693d96ceb2f531fa05db530f3e21517d
    '''

    def __init__(self, mode='min', min_delta=0, patience=10, percentage=False):
        self.mode = mode
        self.min_delta = min_delta
        self.patience = patience
        self.best = None
        self.num_bad_epochs = 0
        self.is_better = None
        self._init_is_better(mode, min_delta, percentage)

        if patience == 0:
            self.is_better = lambda a, b: True
            self.step = lambda a: False

    def step(self, metrics):
        if self.best is None:
            self.best = metrics
            return False

        if np.isnan(metrics):
            return True

        if self.is_better(metrics, self.best):
            self.num_bad_epochs = 0
            self.best = metrics
        else:
            self.num_bad_epochs += 1

        if self.num_bad_epochs >= self.patience:
            return True

        return False

    def _init_is_better(self, mode, min_delta, percentage):
        if mode not in {'min', 'max'}:
            raise ValueError('mode ' + mode + ' is unknown!')
        if not percentage:
            if mode == 'min':
                self.is_better = lambda a, best: a < best - min_delta
            if mode == 'max':
                self.is_better = lambda a, best: a > best + min_delta
        else:
            if mode == 'min':
                self.is_better = lambda a, best: a < best - (
                            best * min_delta / 100)
            if mode == 'max':
                self.is_better = lambda a, best: a > best + (
                            best * min_delta / 100)


class AverageMeter(object):
    """
    Computes and stores the average and current value
    cf. https://github.com/pytorch/examples/blob/master/imagenet/main.py#L296
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


'''
def f1_score_for_thresholds(y_true, proba):
    precision, recall, thresholds = metrics.precision_recall_curve(y_true, proba)
    thresholds = np.append(thresholds, 1.001)
    F1 = 2 / (1 / precision + 1 / recall)
    best_f1 = np.max(F1)
    best_threshold = thresholds[np.argmax(F1)]
    return best_f1, best_threshold
'''
def f1_score_for_thresholds(y_true, proba):
    best_score, best_thresh = 0., 0.
    for thresh in thresholds:
        score = metrics.f1_score(y_true, np.asarray(proba) > thresh)
        if score > best_score:
            best_score = score
            best_thresh = thresh
    return best_score, best_thresh


def step(model, inputs, features, targets, criterion, device):
    inputs, features, targets = inputs.to(device), features.to(device), targets.to(device)  # noqa
    out = model([inputs, features])
    loss = criterion(out, targets)
    return out, loss


def train(model, data_loader, criterion, optimizer, device):
    losses = AverageMeter()
    model.train()
    for inputs, features, targets, index in data_loader:
        bs = inputs.size(0)
        out, loss = step(model, inputs, features, targets, criterion, device)
        losses.update(loss.item(), bs)
        optimizer.zero_grad()
        loss.backward()
        # nn.utils.clip_grad_norm_(net.parameters(), clip)
        optimizer.step()
    return losses.avg


def validate(model, data_loader, criterion, device):
    model.eval()
    losses = AverageMeter()
    outputs, trues = [], []
    with torch.no_grad():
        for inputs, features, targets, index in data_loader:
            bs = inputs.size(0)
            out, loss = step(model, inputs, features, targets, criterion, device)
            losses.update(loss.item(), bs)
            outputs += out.detach().cpu().numpy().tolist()
            trues += targets.detach().numpy().tolist()
    f1, thresh = f1_score_for_thresholds(trues, outputs)
    return {'loss': losses.avg, 'f1': f1, 'thresh': thresh, 'output': np.array(outputs).flatten()}


def test(model, data_loader, device):
    model.eval()
    outputs = []
    with torch.no_grad():
        for inputs, features in data_loader:
            inputs, features = inputs.to(device), features.to(device)
            out = model([inputs, features])
            outputs += out.detach().cpu().numpy().tolist()
    return np.array(outputs).flatten()


def get_coefs(word, *arr):
    return word, np.asarray(arr, dtype='float32')


def get_embedding(path, word_index, name='glove'):
    if name.lower() == 'glove':
        embeddings_index = dict(get_coefs(*o.split(' '))[:300] for o in open(path))
    elif name.lower() == 'fasttext':
        embeddings_index = dict(get_coefs(*o.split(" ")) for o in open(path) if len(o) > 100)
    elif name.lower() == 'paragram':
        embeddings_index = dict(
            get_coefs(*o.split(" "))
            for o in open(path, encoding="utf8", errors='ignore') if len(o) > 100)
    elif name.lower() == 'google':
        loaded = KeyedVectors.load_word2vec_format(path, binary=True)
        embeddings_index = dict([(k, loaded[k]) for k in loaded.vocab.keys()])
    else:
        raise NotImplementedError('No embedding: {}'.format(name))
    logger.info('Created embedding_index.')

    all_embs = np.stack(embeddings_index.values())
    emb_mean, emb_std = all_embs.mean(), all_embs.std()
    emb_size = all_embs.shape[1]
    n_words = min(max_features, len(word_index))
    logger.info('Creating embedding_matrix')
    embedding_matrix = np.random.normal(emb_mean, emb_std, (n_words, emb_size))
    for word, i in tqdm(word_index.items()):
        if i >= max_features:
            continue
        embedding_vector = embeddings_index.get(word)
        if embedding_vector is not None:
            embedding_matrix[i] = embedding_vector
    #     else:
    #         embedding_vector = embeddings_index.get(word.capitalize())
    #         if embedding_vector is not None:
    #             embedding_matrix[i] = embedding_vector
    del embeddings_index, all_embs, embedding_vector
    gc.collect()
    return embedding_matrix


def preprocess_contraction(text, mapping):
    '''
    https://www.kaggle.com/theoviel/improve-your-score-with-text-preprocessing-v2
    '''
    specials = ["’", "‘", "´", "`"]
    for s in specials:
        text = text.replace(s, "'")
    text = ' '.join([mapping[t] if t in mapping else t for t in text.split(" ")])
    return text


def preprocess_punctuation(text, punctuation, mapping):
    '''
    https://www.kaggle.com/theoviel/improve-your-score-with-text-preprocessing-v2
    '''
    specials = {'\u200b': ' ', '…': ' ... ', '\ufeff': '', 'करना': '', 'है': ''}
    for p in mapping:
        text = text.replace(p, mapping[p])
    for p in punctuation:
        text = text.replace(p, f' {p} ')
    for s in specials:
        text = text.replace(s, specials[s])

    return text


def clean_punctuation(x):
    puncts = [',', '.', '"', ':', ')', '(', '-', '!', '?', '|', ';', "'", '$', '&', '/', '[', ']', '>', '%', '=', '#', '*', '+', '\\', '•',  '~', '@', '£',
 '·', '_', '{', '}', '©', '^', '®', '`',  '<', '→', '°', '€', '™', '›',  '♥', '←', '×', '§', '″', '′', 'Â', '█', '½', 'à', '…',
 '“', '★', '”', '–', '●', 'â', '►', '−', '¢', '²', '¬', '░', '¶', '↑', '±', '¿', '▾', '═', '¦', '║', '―', '¥', '▓', '—', '‹', '─',
 '▒', '：', '¼', '⊕', '▼', '▪', '†', '■', '’', '▀', '¨', '▄', '♫', '☆', 'é', '¯', '♦', '¤', '▲', 'è', '¸', '¾', 'Ã', '⋅', '‘', '∞',
 '∙', '）', '↓', '、', '│', '（', '»', '，', '♪', '╩', '╚', '³', '・', '╦', '╣', '╔', '╗', '▬', '❤', 'ï', 'Ø', '¹', '≤', '‡', '√', ]
    x = str(x)
    for punct in puncts:
        x = x.replace(punct, f' {punct} ')
    return x


def clean_number(x):
    x = re.sub('[0-9]{5,}', '#####', x)
    x = re.sub('[0-9]{4}', '####', x)
    x = re.sub('[0-9]{3}', '###', x)
    x = re.sub('[0-9]{2}', '##', x)
    return x


def preprocess_misspell(text, dictinary):
    '''
    https://www.kaggle.com/theoviel/improve-your-score-with-text-preprocessing-v2
    '''
    for word in dictionary.keys():
        text = text.replace(word, dictinary[word])
    return text


def _get_mispell(mispell_dict):
    mispell_re = re.compile('(%s)' % '|'.join(mispell_dict.keys()))
    return mispell_dict, mispell_re


def replace_typical_misspell(text):
    mispell_dict = {"ain't": "is not", "aren't": "are not","can't": "cannot", "'cause": "because", "could've": "could have", "couldn't": "could not", "didn't": "did not",  "doesn't": "does not", "don't": "do not", "hadn't": "had not", "hasn't": "has not", "haven't": "have not", "he'd": "he would","he'll": "he will", "he's": "he is", "how'd": "how did", "how'd'y": "how do you", "how'll": "how will", "how's": "how is",  "I'd": "I would", "I'd've": "I would have", "I'll": "I will", "I'll've": "I will have","I'm": "I am", "I've": "I have", "i'd": "i would", "i'd've": "i would have", "i'll": "i will",  "i'll've": "i will have","i'm": "i am", "i've": "i have", "isn't": "is not", "it'd": "it would", "it'd've": "it would have", "it'll": "it will", "it'll've": "it will have","it's": "it is", "let's": "let us", "ma'am": "madam", "mayn't": "may not", "might've": "might have","mightn't": "might not","mightn't've": "might not have", "must've": "must have", "mustn't": "must not", "mustn't've": "must not have", "needn't": "need not", "needn't've": "need not have","o'clock": "of the clock", "oughtn't": "ought not", "oughtn't've": "ought not have", "shan't": "shall not", "sha'n't": "shall not", "shan't've": "shall not have", "she'd": "she would", "she'd've": "she would have", "she'll": "she will", "she'll've": "she will have", "she's": "she is", "should've": "should have", "shouldn't": "should not", "shouldn't've": "should not have", "so've": "so have","so's": "so as", "this's": "this is","that'd": "that would", "that'd've": "that would have", "that's": "that is", "there'd": "there would", "there'd've": "there would have", "there's": "there is", "here's": "here is","they'd": "they would", "they'd've": "they would have", "they'll": "they will", "they'll've": "they will have", "they're": "they are", "they've": "they have", "to've": "to have", "wasn't": "was not", "we'd": "we would", "we'd've": "we would have", "we'll": "we will", "we'll've": "we will have", "we're": "we are", "we've": "we have", "weren't": "were not", "what'll": "what will", "what'll've": "what will have", "what're": "what are",  "what's": "what is", "what've": "what have", "when's": "when is", "when've": "when have", "where'd": "where did", "where's": "where is", "where've": "where have", "who'll": "who will", "who'll've": "who will have", "who's": "who is", "who've": "who have", "why's": "why is", "why've": "why have", "will've": "will have", "won't": "will not", "won't've": "will not have", "would've": "would have", "wouldn't": "would not", "wouldn't've": "would not have", "y'all": "you all", "y'all'd": "you all would","y'all'd've": "you all would have","y'all're": "you all are","y'all've": "you all have","you'd": "you would", "you'd've": "you would have", "you'll": "you will", "you'll've": "you will have", "you're": "you are", "you've": "you have", 'colour': 'color', 'centre': 'center', 'favourite': 'favorite', 'travelling': 'traveling', 'counselling': 'counseling', 'theatre': 'theater', 'cancelled': 'canceled', 'labour': 'labor', 'organisation': 'organization', 'wwii': 'world war 2', 'citicise': 'criticize', 'youtu ': 'youtube ', 'Qoura': 'Quora', 'sallary': 'salary', 'Whta': 'What', 'narcisist': 'narcissist', 'howdo': 'how do', 'whatare': 'what are', 'howcan': 'how can', 'howmuch': 'how much', 'howmany': 'how many', 'whydo': 'why do', 'doI': 'do I', 'theBest': 'the best', 'howdoes': 'how does', 'mastrubation': 'masturbation', 'mastrubate': 'masturbate', "mastrubating": 'masturbating', 'pennis': 'penis', 'Etherium': 'Ethereum', 'narcissit': 'narcissist', 'bigdata': 'big data', '2k17': '2017', '2k18': '2018', 'qouta': 'quota', 'exboyfriend': 'ex boyfriend', 'airhostess': 'air hostess', "whst": 'what', 'watsapp': 'whatsapp', 'demonitisation': 'demonetization', 'demonitization': 'demonetization', 'demonetisation': 'demonetization'}
    mispellings, mispellings_re = _get_mispell(mispell_dict)
    def replace(match):
        return mispellings[match.group(0)]
    return mispellings_re.sub(replace, text)


def preprocess(df):
    df['question_text'] = df['question_text'].apply(lambda x: x.lower())
    df['question_text'] = df['question_text'].apply(lambda text: clean_punctuation(text))
    df['question_text'] = df['question_text'].apply(lambda text: clean_number(text))
    df['question_text'] = df['question_text'].apply(lambda text: replace_typical_misspell(text))
    return df


def add_features(df):
    df['length'] = df['question_text'].apply(len)
    df['n_capitals'] = df['question_text'].apply(
        lambda text: sum(1 for c in text if c.isupper()))
    df['capitals/length'] = df['n_capitals'] / df['length']
    df['n_words'] = df['question_text'].str.count('\S+')
    df['n_unique_words'] = df['question_text'].apply(
        lambda text: len(set(text.split())))
    df['words/uniques'] = df['n_words'] / df['n_unique_words']
    return df


class DatasetWrapper(Dataset):
    def __init__(self, dataset, features, test=False):
        assert len(dataset) == len(features)
        self.dataset = dataset
        self.features = features
        self.test = test

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, index):
        features = torch.tensor(self.features[index], dtype=torch.float)
        if self.test:
            data = self.dataset[index]
            return data[0], features

        data, target = self.dataset[index]
        return data, features, target, index


def main():
    '''
    # data
    df_train = pd.read_csv('../input/train.csv')
    df_test = pd.read_csv('../input/test.csv')
    # preprocess
    t0 = time()
    df_train = preprocess(df_train)
    df_test = preprocess(df_test)
    X_train = df_train['question_text'].fillna('_na_').values
    X_test = df_test['question_text'].fillna('_na_').values
    logger.info('Preprocessed in {}'.format(time() - t0))
    # features
    df_train = add_features(df_train)
    df_test = add_features(df_test)
    features_train = df_train[['capitals/length', 'words/uniques']].fillna(0)
    features_test = df_test[['capitals/length', 'words/uniques']].fillna(0)
    scaler = StandardScaler()
    scaler.fit(np.vstack([features_train, features_test]))
    features_train = scaler.transform(features_train)
    features_test = scaler.transform(features_test)
    # tokenize
    t0 = time()
    tokenizer = Tokenizer(num_words=max_features)
    tokenizer.fit_on_texts(list(X_train))
    X_train = tokenizer.texts_to_sequences(X_train)
    X_test = tokenizer.texts_to_sequences(X_test)
    logger.info('Tokenized in {}'.format(time() - t0))
    # padding
    t0 = time()
    X_train = pad_sequences(X_train, maxlen=maxlen)
    X_test = pad_sequences(X_test, maxlen=maxlen)
    logger.info('Padding in {}'.format(time() - t0))
    # target
    y_train = df_train['target'].values
    # shuffle
    indices = np.random.permutation(len(X_train))
    X_train, y_train = X_train[indices], y_train[indices]
    features_train = features_train[indices]
    # embedding
    if debug:
        embedding = None
    else:
        embeddings = []
        for name, path in emb_paths.items():
            embeddings.append(get_embedding(path, tokenizer.word_index, name=name))
        embedding = np.mean(embeddings, axis=0)
        del embeddings
        gc.collect()
    logger.info('Created embeddings. Time {:.2f}s'.format(time() - start_time))

    np.save('../input/features_train.npy', features_train)
    np.save('../input/features_test.npy', features_test)
    '''
    X_train = np.load('../input/X_train.npy')
    y_train = np.load('../input/y_train.npy')
    X_test = np.load('../input/X_test.npy')
    embedding = np.load('../input/mean_embedding.npy')
    features_train = np.load('../input/features_train.npy')
    features_test = np.load('../input/features_test.npy')
    logger.info('Loaded data. Time {:.2f}'.format(time() - start_time))

    # data loader
    test_dataset = TensorDataset(torch.from_numpy(X_test.astype('int64')))
    test_dataset = DatasetWrapper(test_dataset, features_test, test=True)
    test_loader = DataLoader(test_dataset, batch_size, shuffle=False)

    proba_train, proba_test = np.zeros(len(X_train)), np.zeros(len(X_test))
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for fold_i, (train_idx, val_idx) in enumerate(skf.split(X_train, y_train)):
        fold_i += 1
        logger.info('Fold {}'.format(fold_i))
        # split
        X_train_fold, y_train_fold = X_train[train_idx].astype('int64'), y_train[train_idx].astype('float32')
        X_val_fold, y_val_fold = X_train[val_idx].astype('int64'), y_train[val_idx].astype('float32')
        train_dataset = TensorDataset(torch.from_numpy(X_train_fold), torch.from_numpy(y_train_fold))
        val_dataset = TensorDataset(torch.from_numpy(X_val_fold), torch.from_numpy(y_val_fold))
        features_train_fold = features_train[train_idx]
        features_val_fold = features_train[val_idx]
        train_dataset = DatasetWrapper(train_dataset, features_train_fold)
        val_dataset = DatasetWrapper(val_dataset, features_val_fold)
        train_loader  = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size, shuffle=False)

        # model
        model = RNNCapsule(
            max_features, embedding_dim=emb_size, embedding=embedding,
            embedding_trainable=embedding_trainable, device=device).to(device)
        # criterion = nn.BCEWithLogitsLoss()
        criterion = nn.BCELoss()
        optimizer = optim.Adam(model.parameters(), lr=lr)
        if early_stopping:
            early_stop = EarlyStopping(mode='min', min_delta=min_delta, patience=patience, percentage=False)

        for epoch_i in range(1, 1 + epochs):
            if debug: break
            message = ''
            if epoch_i == epoch_unfreeze:
                for param in model.parameters():
                    param.requires_grad = True
                optimizer = optim.Adam(model.parameters(), lr=lr / 10)
                message = 'Unfreezed. LR {}'.format(lr / 10)
            loss = train(model, train_loader, criterion, optimizer, device)
            validation = validate(model, val_loader, criterion, device)
            logger.info('Fold {} Epoch {}/{} Train/Loss {:.4f} Val/Loss {:.4f} Val/F1 {:.4f} Threshold {:.2f} {}'.format(
                fold_i, epoch_i, epochs, loss,
                validation['loss'], validation['f1'], validation['thresh'],
                message
                )
            )
            if early_stopping:
                if early_stop.step(validation['loss']):
                    logger.info('Fold {} Early stop'.format(fold_i))
                    break
            if one_epoch: break
        # proba_train[val_idx] = validation['output']
        logger.info('Fold {} Finished training'.format(fold_i))

        proba = test(model, test_loader, device)
        proba_test += proba / n_splits
        logger.info('Fold {} Scored test probabilities'.format(fold_i))
        if one_epoch: break

    # submit
    f1, threshold = f1_score_for_thresholds(y_train, proba_train)
    logger.info('Train/F1/Best {:.4f} (Threshold = {:.2f})'.format(f1, threshold))

    y_pred = (proba_test > threshold).astype('int')
    submit = pd.read_csv('../input/sample_submission.csv')
    submit.prediction = y_pred
    submit.to_csv('submission.csv', index=False)

    elapsed = datetime.now() - start
    logger.info('{}h {}m {}s'.format(*str(elapsed).split(':')))


if __name__ == '__main__':
    main()

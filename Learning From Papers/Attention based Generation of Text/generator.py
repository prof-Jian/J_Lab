# -*- coding: utf-8 -*-

import os
import random

import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

class Generator(nn.Module):
    """Generator """
    def __init__(self, num_emb, emb_dim, hidden_dim, use_cuda,padding_idx = 0):
        super(Generator, self).__init__()
        self.num_emb = num_emb
        self.emb_dim = emb_dim
        self.hidden_dim = hidden_dim
        self.use_cuda = use_cuda
        self.emb = nn.Embedding(num_emb, emb_dim) #num_emb嵌入词典的大小；emb_dim每个嵌入向量的维度；
        # When batch_first is True, then the input and output tensors are provided as (batch, seq, feature).
        self.lstm = nn.LSTM(emb_dim, hidden_dim, batch_first=True) # 为什么不用GRU
        self.lin = nn.Linear(hidden_dim, num_emb)
        self.softmax = nn.LogSoftmax()
        self.init_params()

    def forward(self, x): # 输入一个
        """
        Args:
            x: (batch_size, seq_len), sequence of tokens generated by generator
        """
        emb = self.emb(x)
        h0, c0 = self.init_hidden(x.size(0)) #这里h0, c0没有batch_size first呀,难道batch_first只对input和output起作用
        self.lstm.flatten_parameters()
        output, (h, c) = self.lstm(emb, (h0, c0)) # output:(batch_size,seq_len,hidden_dim)
        pred = self.softmax(self.lin(output.contiguous().view(-1, self.hidden_dim))) #这里不要声明dim吗？要的
        return pred # output:(batch_size * seq_len , num_emb)

    def step(self, x, h, c):
        """
        Args:
            x: (batch_size,  1), sequence of tokens generated by generator
            h: (1, batch_size, hidden_dim), lstm hidden state
            c: (1, batch_size, hidden_dim), lstm cell state
        """
        emb = self.emb(x)
        self.lstm.flatten_parameters()
        output, (h, c) = self.lstm(emb, (h, c))
        pred = F.softmax(self.lin(output.view(-1, self.hidden_dim)), dim=1) # 为什么这里不加contiguous？难道是因为每次x的seq_len = 1
        return pred, h, c


    def init_hidden(self, batch_size):
        h = Variable(torch.zeros((1, batch_size, self.hidden_dim)))
        c = Variable(torch.zeros((1, batch_size, self.hidden_dim)))
        if self.use_cuda:
            h, c = h.cuda(), c.cuda()
        return h, c

    def init_params(self):
        for param in self.parameters():
            param.data.uniform_(-0.05, 0.05)

    def sample(self, batch_size, seq_len, x=None): # 根据已经训练好的网络，sample出一句seq_len长度的句子；
        res = []
        flag = False # whether sample from zero
        if x is None:
            flag = True
        if flag:
            x = Variable(torch.zeros((batch_size, 1)).long())
        if self.use_cuda:
            x = x.cuda()
        h, c = self.init_hidden(batch_size)
        samples = []
        if flag:
            for i in range(seq_len):
                output, h, c = self.step(x, h, c) #output:(batch_size,num_emb)
                x = output.multinomial(1) #一定概率给出数值最大的那个数的下标，()
                samples.append(x)
        else: # 如果是给定一段话的开头；
            given_len = x.size(1)
            lis = x.chunk(x.size(1), dim=1)
            for i in range(given_len): #前面几个字用来训练h和c
                output, h, c = self.step(lis[i], h, c)
                samples.append(lis[i])
            x = output.multinomial(1) #最后一个output作为x作为下阶段的起点
            for i in range(given_len, seq_len):
                samples.append(x)
                output, h, c = self.step(x, h, c)
                x = output.multinomial(1)
        output = torch.cat(samples, dim=1)
        return output

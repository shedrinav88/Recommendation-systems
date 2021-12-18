# -*- coding: utf-8 -*-
"""recommenders

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1FCEn8rSFobGboKSr07-tLQVqtqSXkk5E
"""

import pandas as pd
import numpy as np

# Для работы с матрицами
from scipy.sparse import csr_matrix

# Матричная факторизация
from implicit.als import AlternatingLeastSquares
from implicit.nearest_neighbours import ItemItemRecommender  # нужен для одного трюка
from implicit.nearest_neighbours import bm25_weight, tfidf_weight


class MainRecommender:
    """Рекоммендации, которые можно получить из ALS
    
    Input
    -----
    user_item_matrix: pd.DataFrame
        Матрица взаимодействий user-item
    """
    
    def __init__(self, data, weighting=True):
        
        # your_code. Это не обязательная часть. Но если вам удобно что-либо посчитать тут - можно это сделать
        self.popularity = data.groupby(['user_id', 'item_id'])['quantity'].count().reset_index()
        self.user_item_matrix = self.prepare_matrix(data)  # pd.DataFrame
        self.id_to_itemid, self.id_to_userid, self.itemid_to_id, \
        self.userid_to_id = self.prepare_dicts(self.user_item_matrix)
        
        if weighting:
            self.user_item_matrix = bm25_weight(self.user_item_matrix.T).T 
        
        self.model = self.fit(self.user_item_matrix)
        self.own_recommender = self.fit_own_recommender(self.user_item_matrix)
     
    @staticmethod
    def prepare_matrix(data, index='user_id', column='item_id', 
                       value='quantity', func='count'):
        """Подготавливает user_item матрицу из тренировочной выборки"""
        user_item_matrix = pd.pivot_table(data, index=index, columns=column,
                                          values=value, aggfunc=func,fill_value=0)

        user_item_matrix = user_item_matrix.astype(float) # необходимый тип матрицы для implicit

        return user_item_matrix
    
    @staticmethod
    def prepare_dicts(user_item_matrix):
        """Подготавливает вспомогательные словари"""
        
        userids = user_item_matrix.index.values
        itemids = user_item_matrix.columns.values

        matrix_userids = np.arange(len(userids))
        matrix_itemids = np.arange(len(itemids))

        id_to_itemid = dict(zip(matrix_itemids, itemids))
        id_to_userid = dict(zip(matrix_userids, userids))

        itemid_to_id = dict(zip(itemids, matrix_itemids))
        userid_to_id = dict(zip(userids, matrix_userids))
        
        return id_to_itemid, id_to_userid, itemid_to_id, userid_to_id
     
    @staticmethod
    def fit_own_recommender(user_item_matrix):
        """Обучает модель, которая рекомендует товары, среди товаров, купленных юзером"""
    
        own_recommender = ItemItemRecommender(K=1, num_threads=4)
        own_recommender.fit(csr_matrix(user_item_matrix).T.tocsr())
        
        return own_recommender
    
    @staticmethod
    def fit(user_item_matrix, n_factors=20, regularization=0.001, 
            use_gpu=False, iterations=15, num_threads=0):
        """Обучает ALS"""
        
        model = AlternatingLeastSquares(factors=n_factors, 
                                             regularization=regularization,
                                             iterations=iterations, 
                                             use_gpu=use_gpu,  
                                             num_threads=num_threads)
        model.fit(csr_matrix(user_item_matrix).T.tocsr())
        
        return model

    def get_similar_items_recommendation(self, user, N=5):
        """Рекомендуем товары, похожие на топ-N купленных юзером товаров"""


        self.popularity.sort_values('quantity', ascending=False, inplace=True)
        self.popularity = self.popularity[self.popularity['item_id'] != 999999]
        self.popularity.sort_values(by=['user_id','quantity'], ascending=False, inplace=True)  
        pop_items = self.popularity['item_id'][self.popularity['user_id'] == user].to_numpy()[:N]

        res = []
        for item in pop_items:
            similar_items = self.model.similar_items(self.itemid_to_id[item], N=2)
            res.append(self.id_to_itemid[similar_items[1][0]]) 

        assert len(res) == N, 'Количество рекомендаций != {}'.format(N)
        return res
    
    def get_similar_users_recommendation(self, user, N=5):
        """Рекомендуем топ-N товаров, среди купленных похожими юзерами"""

        similar_users = self.model.similar_users(self.userid_to_id[user], N=(N+1))
        similar_users = similar_users[1:]

        res = []
        for sim in similar_users:
            res.append(self.id_to_itemid[self.own_recommender.recommend(userid=self.userid_to_id[sim[0]], 
                              user_items=csr_matrix(self.user_item_matrix).tocsr(),
                              N=1,
                            filter_already_liked_items=False, 
                            filter_items=None, 
                            recalculate_user=False)[0][0]])

        assert len(res) == N, 'Количество рекомендаций != {}'.format(N)
        return res
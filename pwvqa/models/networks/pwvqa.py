import torch
import torch.nn as nn
from block.models.networks.mlp import MLP
from .utils import grad_mul_const # mask_softmax, grad_reverse, grad_reverse_mask, 

eps = 5e-11

class PWVQA(nn.Module):
    """
    Wraps another model
    The original model must return a dictionnary containing the 'logits' key (predictions before softmax)
    Returns:
        - logits_vq: the original predictions of the model, i.e., NIE
        - logits_q: the predictions from the question-only branch
        - logits_v: the predictions from the vision-only branch
        - logits_all: the predictions from the ensemble model
        - logits_pwvqa: the predictions based on PW-VQA, i.e., TIE
    => Use `logits_all`, `logits_q` and `logits_v` for the loss
    """
    def __init__(self, model, output_size, classif_q, classif_v, fusion_mode, end_classif=True, is_va=True):
        super().__init__()
        self.net = model
        self.end_classif = end_classif

        assert fusion_mode == 'ea', "Fusion mode should be ea."
        self.fusion_mode = fusion_mode
        self.is_va = is_va
            
        # Q->A branch
        self.q_1 = MLP(**classif_q)
        if self.end_classif:
            self.q_2 = nn.Linear(output_size, output_size)

        # V->A branch
        if self.is_va: # default: True (containing V->A)
            self.v_1 = MLP(**classif_v)
            if self.end_classif:
                self.v_2 = nn.Linear(output_size, output_size)

        self.constant = nn.Parameter(torch.tensor(0.0))

    def forward(self, batch):
        out = {}
        # model prediction
        net_out = self.net(batch)
        logits = net_out['logits']

        # Q->A branch
        q_embedding = net_out['q_emb']  # N * q_emb
        q_embedding = grad_mul_const(q_embedding, 0.0) # don't backpropagate
        q_pred = self.q_1(q_embedding)

        # V->A branch
        if self.is_va:
            v_embedding = net_out['v_emb']  # N * v_emb
            v_embedding = grad_mul_const(v_embedding, 0.0) # don't backpropagate
            v_pred = self.v_1(v_embedding)
        else:
            v_pred = None

        # both q, k and v are the facts
        z_qkv = self.fusion(logits, q_pred, v_pred, q_fact=True,  k_fact=True, v_fact=True) # te
        # v, q are the facts while k is the counterfactuals
        z_vq = self.fusion(logits, q_pred, v_pred, q_fact=True,  k_fact=False, v_fact=True) # nie
        
        logits_pwvqa = z_qkv - z_vq

        if self.end_classif:
            q_out = self.q_2(q_pred)
            if self.is_va:
                v_out = self.v_2(v_pred)
        else:
            q_out = q_pred
            if self.is_va:
                v_out = v_pred

        out['logits_all'] = z_qkv # for optimization
        out['logits_vq']  = logits # predictions of the original VQ branch, i.e., NIE
        out['logits_pwvqa'] = logits_pwvqa # predictions of PWVQA, i.e., TIE
        out['logits_q'] = q_out # for optimization
        if self.is_va:
            out['logits_v'] = v_out # for optimization

        if self.is_va:
            out['z_nde'] = self.fusion(logits.clone().detach(), q_pred.clone().detach(), v_pred.clone().detach(), q_fact=True,  k_fact=False, v_fact=False) # tie
        else:
            out['z_nde'] = self.fusion(logits.clone().detach(), q_pred.clone().detach(), None, q_fact=True,  k_fact=False, v_fact=False) # tie
        
        return out

    def process_answers(self, out, key=''):
        out = self.net.process_answers(out, key='_all')
        out = self.net.process_answers(out, key='_vq')
        out = self.net.process_answers(out, key='_pwvqa')
        out = self.net.process_answers(out, key='_q')
        if self.is_va:
            out = self.net.process_answers(out, key='_v')
        return out

    def fusion(self, z_k, z_q, z_v, q_fact=False, k_fact=False, v_fact=False):

        z_k, z_q, z_v = self.transform(z_k, z_q, z_v, q_fact, k_fact, v_fact)

        if self.fusion_mode == 'ea':
            if self.is_va:
                z1= z_k * z_q + z_k * z_v + z_q * z_v
                z2 = z_k * z_q * z_v
                alpha = 1.5
            else:
                z1= z_k * z_q 
                z2 = z_k * z_q
                alpha = 1.5
            z = 1/(alpha+1) * torch.log(z1 + eps) + 1/(alpha+1) * torch.log(torch.pow(z2, alpha) + eps)

        return z

    def transform(self, z_k, z_q, z_v, q_fact=False, k_fact=False, v_fact=False):  

        if not k_fact:
            z_k = self.constant * torch.ones_like(z_k).cuda()

        if not q_fact:
            z_q = self.constant * torch.ones_like(z_q).cuda()

        if self.is_va:
            if not v_fact:
                z_v = self.constant * torch.ones_like(z_v).cuda()

        if self.fusion_mode == 'ea':
            z_k = torch.sigmoid(z_k)
            z_q = torch.sigmoid(z_q)
            if self.is_va:
                z_v = torch.sigmoid(z_v)

        return z_k, z_q, z_v
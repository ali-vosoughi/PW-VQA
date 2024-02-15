from bootstrap.lib.options import Options
from block.models.criterions.vqa_cross_entropy import VQACrossEntropyLoss
from .pwvqa_criterion import PWVQACriterion

def factory(engine, mode):
    name = Options()['model.criterion.name']
    split = engine.dataset[mode].split
    eval_only = 'train' not in engine.dataset
    
    opt = Options()['model.criterion']
    if split == "test" and 'tdiuc' not in Options()['dataset.name']:
        return None
    if name == 'vqa_cross_entropy':
        criterion = VQACrossEntropyLoss()

    elif name == "pwvqa_criterion":
        criterion = PWVQACriterion(
            question_loss_weight=opt['question_loss_weight'],
            vision_loss_weight=opt['vision_loss_weight'],
            is_va=True
        )
    else:
        raise ValueError(name)
    return criterion

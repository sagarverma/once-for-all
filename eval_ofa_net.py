# Once for All: Train One Network and Specialize it for Efficient Deployment
# Han Cai, Chuang Gan, Tianzhe Wang, Zhekai Zhang, Song Han
# International Conference on Learning Representations (ICLR), 2020.

import os
import torch
import argparse

from ofa.imagenet_classification.data_providers.practical_dl import PracticalDLDataProvider
from ofa.imagenet_classification.run_manager import PracticalDLRunConfig, RunManager
from ofa.imagenet_classification.elastic_nn.networks import OFAMobileNetV3


parser = argparse.ArgumentParser()
parser.add_argument(
    "-p", "--path", help="The path of Practical DL", type=str, default="./data/PracticalDL"
)
parser.add_argument("-g", "--gpu", help="The gpu(s) to use", type=str, default="all")
parser.add_argument(
    "-b",
    "--batch-size",
    help="The batch on every device for validation",
    type=int,
    default=100,
)
parser.add_argument("-j", "--workers", help="Number of workers", type=int, default=20)
parser.add_argument("-w", "--weight", help="weight path", required=True, type=str)
parser.add_argument("-s", "--img_size", help="Input image size", default=76, type=int)
parser.add_argument("--save_weight", help="Path where weight should be saved", default=None)

args = parser.parse_args()
if args.gpu == "all":
    device_list = range(torch.cuda.device_count())
    args.gpu = ",".join(str(_) for _ in device_list)
else:
    device_list = [int(_) for _ in args.gpu.split(",")]
os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
args.batch_size = args.batch_size * max(len(device_list), 1)
PracticalDLDataProvider.DEFAULT_PATH = args.path

# ofa_network = ofa_net(args.net, pretrained=True)
ofa_network = OFAMobileNetV3(
            dropout_rate=0,
            width_mult=1.0,
            ks_list=[3, 5, 7],
            expand_ratio_list=[3, 4, 6],
            depth_list=[2, 3, 4],
        )
init = torch.load(args.weight, map_location="cpu")["state_dict"]
ofa_network.load_state_dict(init)

run_config = PracticalDLRunConfig(test_batch_size=args.batch_size, n_worker=args.workers)

""" Randomly sample a sub-network, 
    you can also manually set the sub-network using: 
        ofa_network.set_active_subnet(ks=7, e=6, d=4) 
"""
# ofa_network.sample_active_subnet()
ofa_network.set_active_subnet(ks=7, e=4, d=4)
subnet = ofa_network.get_active_subnet(preserve_weight=True)

""" Test sampled subnet 
"""
run_manager = RunManager(".tmp/eval_subnet", subnet, run_config, init=False)
# assign image size: 128, 132, ..., 224
run_config.data_provider.assign_active_img_size(args.img_size)
run_manager.reset_running_statistics(net=subnet)

print("Test random subnet:")
print(subnet.module_str)

loss, (top1, top5) = run_manager.validate(net=subnet)
print("Results: loss=%.5f,\t top1=%.1f,\t top5=%.1f" % (loss, top1, top5))

if args.save_weight:
    torch.onnx.export(subnet, 
                      torch.randn(1, 3, args.img_size, args.img_size).cuda(), 
                      args.save_weight)
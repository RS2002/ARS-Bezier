from environment import Env
from ARS import ARS
import argparse
import os
os.environ['KMP_DUPLICATE_LIB_OK']='True'

def get_args():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument("--cpu", action="store_true",default=False)
    parser.add_argument("--cuda", type=str, default='0')

    parser.add_argument('--modelPath', type=str, default="./models/mytest2.xml")
    parser.add_argument('--parameterPath', type=str, default="./result/success/random/complex/ARS.pkl")

    parser.add_argument('--state_dim', type=int, default=31)
    parser.add_argument('--action_dim', type=int, default=12)
    parser.add_argument('--max_steps', type=int, default=5000) # 每个episode内的最大步数
    parser.add_argument('--max_epoch', type=int, default=10000) # 最大训练epoch
    parser.add_argument('--episode_num', type=int, default=16) # 每个epoch内的episode数目
    parser.add_argument('--update_num', type=int, default=10) # 每个epoch内更新的episode数目
    parser.add_argument('--learning_rate', type=float, default=0.03)
    parser.add_argument('--exploration_noise', type=float, default=0.05)

    args = parser.parse_args()
    return args


def main():
    args=get_args()
    if args.rand_env:
        args.modelPath="./models/my_test.xml"
    env=Env(modelPath=args.modelPath,max_steps=args.max_steps,view=True,rand=args.rand_env)
    ars=ARS(state_dim=args.state_dim,action_dim=args.action_dim,env=env,max_epoch=args.max_epoch,episode_num=args.episode_num,update_num=args.update_num,learning_rate=args.learning_rate,exploration_noise=args.exploration_noise)
    ars.load(args.parameterPath)
    ars.eval()
    # env.drawPath()
    # env.write_log()

if __name__ == '__main__':
    main()
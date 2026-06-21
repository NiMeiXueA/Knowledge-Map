const CATEGORIES = [
  {
    "id": "optimization",
    "name": "基础联邦优化",
    "folder": "01_基础联邦优化",
    "why": "这一类方法解决的是联邦学习最底层的训练机制问题：客户端怎么本地更新、服务端怎么聚合、怎样在通信受限且数据非独立同分布的情况下让训练稳定收敛。没有这条主线，后续个性化、蒸馏、提示学习等更复杂方法都缺少一个可靠的训练底座。",
    "advantages": "优点在于问题定义清晰、可迁移性强，很多方法可以直接作为其他联邦框架的优化内核。它们通常有比较扎实的理论收敛分析，也更容易成为后续工作的默认基线。",
    "disadvantages": "缺点是这类方法往往主要改善训练稳定性和通信效率，对个体客户的差异化需求照顾不足；当模型结构异构、任务异构或基础模型引入后，仅靠优化层面的改动通常不够。"
  },
  {
    "id": "personalization",
    "name": "个性化联邦学习",
    "folder": "02_个性化联邦学习",
    "why": "这类方法的核心动机是“一个全局模型无法同时适配所有客户端”。当每个客户端的数据分布、标签偏好、设备能力乃至任务目标不同，个性化联邦学习通过拆分共享参数与私有参数、元学习、对比学习或客户关系建模来提升本地表现。",
    "advantages": "优点是能够更直接应对 non-IID 数据，通常能显著提升每个客户端的本地精度与鲁棒性，也更符合真实应用中“因人而异”或“因机构而异”的需求。",
    "disadvantages": "缺点是方法设计更复杂，模型和训练状态更难统一管理；个性化越强，跨客户端共享的知识可能越少，泛化能力和扩展性需要额外平衡。"
  },
  {
    "id": "distillation",
    "name": "知识蒸馏与异构联邦",
    "folder": "03_知识蒸馏与异构联邦",
    "why": "当客户端模型结构不同、通信预算紧张、或不希望直接上传完整梯度/权重时，蒸馏类方法提供了更灵活的知识传递方式。它们通常把“参数同步”替换成“预测分布、原型、特征或中间知识”的共享。",
    "advantages": "优点是天然适配模型异构、通信高压和隐私敏感场景，也常常能把联邦学习与原型学习、表示学习、生成建模结合起来，扩展空间很大。",
    "disadvantages": "缺点是蒸馏目标、温度、伪数据质量和原型质量都很敏感；如果蒸馏知识本身带偏，或者跨客户端语义未对齐，性能可能不稳定。"
  },
  {
    "id": "graph",
    "name": "图联邦学习",
    "folder": "04_图联邦学习",
    "why": "图联邦学习处理的是节点、边、子图和关系结构天然重要的任务，例如金融风控、推荐、社交网络和分子分析。它不仅要处理联邦异构，还要处理图结构本身的尺度差异和关系稀疏问题。",
    "advantages": "优点是能把拓扑信息纳入协同训练，很多方法会显式建模客户端之间的关系图或图样本本身的结构信息，因此更适合非欧几里得数据。",
    "disadvantages": "缺点是图数据分布更复杂，客户端之间不仅样本分布不同，连图规模、图密度和图语义都可能不同；算法设计和系统实现门槛都更高。"
  },
  {
    "id": "generative",
    "name": "生成式与扩散联邦",
    "folder": "05_生成式与扩散联邦",
    "why": "这条路线关注如何在不集中数据的前提下训练生成模型，尤其是扩散模型，并把生成能力反过来用于缓解异构性或实现 one-shot 联邦。它体现了联邦学习从判别式训练走向生成式协同的扩展。",
    "advantages": "优点是生成模型能承担数据补偿、伪样本合成、隐私增强与通信压缩等多重角色，对于数据稀缺或一次通信场景很有吸引力。",
    "disadvantages": "缺点是训练开销大、参数量大、稳定性要求高，而且生成质量直接影响联邦训练效果；在差分隐私约束下，这类方法尤其容易出现质量衰减。"
  },
  {
    "id": "prompt",
    "name": "联邦提示学习与基础模型",
    "folder": "06_联邦提示学习与基础模型",
    "why": "当基础模型已经具备强大的通用能力时，没必要再在联邦场景里同步整个大模型参数。提示学习路线通过只训练软提示、适配器或轻量模块，把联邦优化对象从“大模型本体”迁移到“小而可协作的控制参数”。",
    "advantages": "优点是通信成本低、收敛更快、对小样本客户端更友好，并且可以借用基础模型已有知识，显著提升冷启动和低资源场景的可用性。",
    "disadvantages": "缺点是高度依赖基础模型质量和任务适配能力；提示参数虽然轻量，但解释性弱，且在跨域和极端异构情况下未必足以覆盖全部个性化需求。"
  },
  {
    "id": "system",
    "name": "系统优化与应用部署",
    "folder": "07_系统优化与应用部署",
    "why": "联邦学习要真正落地，除了算法本身，还必须处理带宽、计算、调度、在线服务和移动性等系统问题。这一类工作把研究视角从“模型怎么学”推进到“系统怎么跑、怎么稳定服务”。",
    "advantages": "优点是更贴近真实部署，能把算法性能和资源利用率、服务效用、在线调度等指标统一考虑，具有很强的工程价值。",
    "disadvantages": "缺点是系统假设较多，复现实验往往依赖复杂平台；此外系统优化方法的收益有时强依赖场景配置，不一定能无缝迁移到其他部署环境。"
  },
  {
    "id": "survey",
    "name": "综述、公平性与背景理论",
    "folder": "08_综述_公平性_背景理论",
    "why": "这类论文帮助建立问题地图和理论背景。一方面，联邦公平性综述让我们看到 FL 在不同群体、能力差异和敏感属性上的挑战；另一方面，蒸馏和多模态对齐等背景论文提供了很多后续联邦方法的设计来源。",
    "advantages": "优点是能快速形成知识框架，特别适合写开题、综述或技术路线分析时用来搭建全局视角和术语体系。",
    "disadvantages": "缺点是这类论文通常不直接给出可部署算法，更多提供问题定义、分类标准和研究空白，因此需要与具体方法论文搭配阅读。"
  }
];

const PAPERS = [
  {
    "id": "fedavg",
    "short": "FedAvg",
    "title": "Communication-Efficient Learning of Deep Networks from Decentralized Data",
    "year": 2017,
    "first_author": "H. Brendan McMahan",
    "venue": "AISTATS 2017",
    "idea": "通过多步本地 SGD 后再做参数平均，建立联邦学习最经典的迭代聚合范式。",
    "categories": [
      "optimization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\FedAvg.pdf",
    "innovation": "FedAvg 把“每轮只做一次分布式同步”改成“客户端本地多步更新 + 服务端周期性平均”，在不上传原始数据的前提下显著减少通信轮数。它不是单纯的工程折中，而是把本地计算正式引入到分布式学习主流程中，成为后续大量联邦算法的共同起点。它的真正贡献在于定义了联邦学习的标准训练接口：采样客户端、下发全局模型、本地训练、回传更新、加权聚合。",
    "flow_steps": [
      "服务器初始化全局模型并抽样客户端",
      "每个客户端在本地数据上执行多轮 SGD",
      "客户端上传模型参数或增量",
      "服务器按数据量加权平均得到新全局模型",
      "重复迭代直到收敛"
    ],
    "applications": "FedAvg 特别适合输入法、移动视觉、边缘推荐等拥有大量终端设备的数据协同场景。它的实现简单、部署门槛低，因此常被当作工业系统中的第一版联邦原型，也是许多个性化、蒸馏和安全方法的基础骨架。",
    "limitations": "FedAvg 在数据高度 non-IID 时容易出现 client drift，本地训练越激进，漂移越明显。它默认所有客户端模型同构，也没有直接处理客户端能力差异、异步训练和极端不均衡参与的问题，因此在真实复杂场景中往往需要被进一步修正。"
  },
  {
    "id": "fedprox",
    "short": "FedProx",
    "title": "Federated Optimization in Heterogeneous Networks",
    "year": 2020,
    "first_author": "Tian Li",
    "venue": "MLSys 2020",
    "idea": "在客户端局部目标中加入 proximal 正则项，约束本地模型不要偏离全局模型过远。",
    "categories": [
      "optimization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\FedProx.pdf",
    "innovation": "FedProx 的核心创新是把异构环境中的训练不稳定性转化为一个局部优化约束问题。它在每个客户端的目标函数中加入与全局模型的距离惩罚，使客户端即便执行不同强度的本地训练，也不会无限制偏离共享方向。这样既能容忍系统异构带来的不同步计算，又能缓解统计异构造成的训练震荡。",
    "flow_steps": [
      "服务器广播全局模型",
      "客户端构造含 proximal 项的局部目标",
      "本地执行若干步优化并允许不同工作量",
      "上传更新至服务器",
      "服务器聚合并进入下一轮"
    ],
    "applications": "FedProx 适合设备性能差异大、部分客户端可能提前停止或本地 epoch 数不一致的联邦网络，例如跨医院、跨企业或边缘计算节点联合训练。它常用于异构性强的现实数据集，作为比 FedAvg 更稳健的优化基线。",
    "limitations": "FedProx 主要解决的是优化稳定性而非个性化本身，因此对本地最终精度的提升依赖场景。proximal 系数需要调节，约束过强会抑制本地适应，约束过弱又不足以控制漂移。"
  },
  {
    "id": "scaffold",
    "short": "SCAFFOLD",
    "title": "SCAFFOLD: Stochastic Controlled Averaging for Federated Learning",
    "year": 2020,
    "first_author": "Sai Praneeth Karimireddy",
    "venue": "ICML 2020",
    "idea": "通过控制变量校正客户端漂移，用方差缩减思想提升联邦优化稳定性。",
    "categories": [
      "optimization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\scaffold.pdf",
    "innovation": "SCAFFOLD 将联邦学习中的 client drift 视为一种有偏更新问题，并引入服务器与客户端两侧的控制变量来对局部梯度方向进行纠偏。这个设计把经典方差缩减思想移植到联邦环境中，使得在 non-IID 数据下，本地训练不再单纯沿着“本地偏好”走偏，而是始终被拉回到更一致的全局方向。",
    "flow_steps": [
      "初始化全局模型和控制变量",
      "服务器下发模型与全局控制量",
      "客户端本地更新时用控制量修正梯度方向",
      "客户端回传模型和局部控制量",
      "服务器同步更新全局模型与控制变量"
    ],
    "applications": "当客户端采样稀疏、数据差异大且通信轮数受限时，SCAFFOLD 往往比纯加权平均更稳。它适合作为算法分析或高异构实验中的强基线，也常被作为后续个性化方法的优化底层。",
    "limitations": "SCAFFOLD 需要额外维护控制变量，状态开销和实现复杂度高于 FedAvg。若系统希望极简部署，或者客户端状态难以长期维护，它的工程成本会明显上升。"
  },
  {
    "id": "fedadam",
    "short": "FedAdam",
    "title": "Adaptive Federated Optimization",
    "year": 2021,
    "first_author": "Sashank J. Reddi",
    "venue": "ICLR 2021",
    "idea": "把 Adam/Yogi/Adagrad 一类自适应优化器迁移到服务端聚合阶段。",
    "categories": [
      "optimization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\FedAdam.pdf",
    "innovation": "FedAdam 不是只改客户端，而是把自适应优化器的思想放到服务器端更新规则里，让服务端根据历轮更新的一阶、二阶统计自适应调节聚合步长。这样做使联邦优化不再依赖一个脆弱的全局固定学习率，而能根据异构噪声和训练阶段自动调整更新强度。",
    "flow_steps": [
      "客户端本地训练得到模型差分",
      "服务器汇总差分形成伪梯度",
      "服务器维护一阶与二阶动量统计",
      "用 Adam/Yogi 风格规则更新全局模型",
      "继续下一轮客户端采样"
    ],
    "applications": "FedAdam 尤其适合深模型或大规模 cross-device 场景，在学习率难调、收敛不稳定时常能带来更顺滑的训练轨迹。它也常与 FedAvg、FedProx 形成对照，说明“优化器选择”本身就是联邦性能的重要因素。",
    "limitations": "自适应优化器虽然更灵活，但也引入了额外超参数和服务器状态。若数据分布极不稳定或客户端参与噪声很大，动量统计可能出现滞后，从而带来新的调参负担。"
  },
  {
    "id": "perfedavg",
    "short": "Per-FedAvg",
    "title": "Personalized Federated Learning with Theoretical Guarantees: A Model-Agnostic Meta-Learning Approach",
    "year": 2020,
    "first_author": "Alireza Fallah",
    "venue": "NeurIPS 2020",
    "idea": "把联邦学习建模成元学习问题，让全局模型成为每个客户端易于快速适配的初始化。",
    "categories": [
      "personalization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\Per-FedAvg.pdf",
    "innovation": "Per-FedAvg 的关键转向是：不再追求对所有客户端都“直接可用”的统一模型，而是学习一个“容易被每个客户端快速微调”的共享初始化。它借用了 MAML 的思想，将个性化能力嵌入训练目标本身，因此联邦训练的终点不再只是全局平均最优，而是“适配友好”的起点最优。",
    "flow_steps": [
      "服务器维护共享初始化模型",
      "客户端在本地执行内层更新完成快速适配",
      "基于适配后的表现构造元梯度",
      "服务器聚合元梯度更新初始化",
      "新客户端也可从该初始化快速个性化"
    ],
    "applications": "Per-FedAvg 很适合用户习惯差异明显但单个客户端样本有限的场景，如个性化输入法、医疗机构个体建模或推荐系统用户偏好学习。它在“新客户端冷启动”问题上也比纯全局模型更有吸引力。",
    "limitations": "元学习目标更复杂，对二阶信息近似、内外层步长都较敏感。若客户端数据分布差异极端或任务本身并不共享一个良好初始化，Per-FedAvg 的收益会被削弱。"
  },
  {
    "id": "fedrep",
    "short": "FedRep",
    "title": "Exploiting Shared Representations for Personalized Federated Learning",
    "year": 2021,
    "first_author": "Liam Collins",
    "venue": "ICML 2021",
    "idea": "学习跨客户端共享的表示层，同时为每个客户端保留私有任务头。",
    "categories": [
      "personalization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedRep.pdf",
    "innovation": "FedRep 认为很多 non-IID 场景中差异集中在决策边界而不是底层特征，因此可以把模型分成共享表示层和客户端私有头部。它把‘哪些知识应该共享’这一问题结构化成模型分层共享，从而比整模型平均更细粒度，也比完全分离训练更能保留协作收益。",
    "flow_steps": [
      "拆分模型为共享 backbone 与本地 head",
      "客户端先更新本地 head 再协同更新共享表示",
      "服务器只聚合共享表示参数",
      "客户端保留各自 head 不上传",
      "迭代形成共享表示与个体决策边界"
    ],
    "applications": "FedRep 很适合图像分类、文本分类等底层特征可共享但标签偏好和类别边界因客户端而异的任务。它也是后续大量层级个性化、模块化联邦方法的重要参考。",
    "limitations": "方法依赖“共享表示可迁移”这一假设；如果客户端之间连底层特征模式都差异很大，强行共享 backbone 反而会限制个体性能。此外共享层与私有层如何切分并没有统一答案。"
  },
  {
    "id": "moon",
    "short": "MOON",
    "title": "Model-Contrastive Federated Learning",
    "year": 2021,
    "first_author": "Qinbin Li",
    "venue": "CVPR 2021",
    "idea": "通过模型级对比学习约束本地表示，让客户端训练既靠近全局模型又远离过时本地模型。",
    "categories": [
      "personalization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\MOON.pdf",
    "innovation": "MOON 把对比学习从样本空间搬到了模型表示空间。它在客户端本地训练时同时考虑当前局部模型、上一轮全局模型与历史局部模型之间的关系，通过对比损失抑制本地模型过度偏离全局语义，从而在不显式做参数拆分的情况下缓解 non-IID 数据带来的漂移。",
    "flow_steps": [
      "服务器下发最新全局模型",
      "客户端保留历史本地模型快照",
      "当前批次同时计算监督损失与模型对比损失",
      "上传更新到服务器聚合",
      "下一轮继续用对比关系约束本地训练"
    ],
    "applications": "MOON 适合视觉任务和表示学习特征较明显的联邦场景，也常作为“无需复杂结构改动就能提升异构鲁棒性”的代表方法。它在实验中经常被用来和 FedProx、SCAFFOLD 一起比较。",
    "limitations": "对比项的温度、负样本构造和表征层选择都比较敏感。它主要是一种训练正则化思路，不像显式个性化方法那样直接为每个客户端保留独立模块，因此个体差异极强时效果可能有限。"
  },
  {
    "id": "fedas",
    "short": "FedAS",
    "title": "FedAS: Bridging Inconsistency in Personalized Federated Learning",
    "year": 2024,
    "first_author": "Xiyuan Yang",
    "venue": "Preprint 2024",
    "idea": "针对个性化参数与共享参数不同步、以及落后客户端训练不足的问题做一致性校正。",
    "categories": [
      "personalization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedAS.pdf",
    "innovation": "FedAS 将个性化联邦中的两类不一致性显式挑出来：一类是同一客户端内部共享参数与个性化参数更新节奏不同，另一类是不同客户端之间由于参与频率差异造成的训练程度不一致。论文的贡献在于把这些常被当作训练噪声的问题上升为核心建模对象，并据此设计协调机制，让个性化与协作不再彼此掣肘。",
    "flow_steps": [
      "区分共享参数与个性化参数",
      "本地训练时对两类参数做协同更新",
      "针对低频参与客户端引入补偿或对齐策略",
      "服务器继续聚合共享部分",
      "整体缓解内外两层不一致性"
    ],
    "applications": "FedAS 适合真实设备参与不稳定、客户端掉线频繁且又希望做个性化建模的环境，例如移动终端、医疗多机构和物联网场景。它对解决‘有些客户端总是跟不上’这一实际问题很有针对性。",
    "limitations": "由于同时处理多类不一致性，算法设计和超参数更多，实现也更复杂。若客户端参与本身已经比较稳定，这类补偿机制的额外收益可能没有那么显著。"
  },
  {
    "id": "feddbe",
    "short": "FedDBE",
    "title": "Eliminating Domain Bias for Federated Learning in Representation Space",
    "year": 2024,
    "first_author": "Jianqing Zhang",
    "venue": "Preprint 2024",
    "idea": "在表示空间消除客户端域偏置，缓解表示退化和跨域迁移困难。",
    "categories": [
      "personalization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedDBE.pdf",
    "innovation": "FedDBE 认为很多联邦异构并不是简单的标签比例偏移，而是更深层的域偏置和表示退化。它把优化重点从参数空间转移到表示空间，通过双向知识传递削弱服务器与客户端之间的域差异，使共享表示不再被局部域特征牵着走。",
    "flow_steps": [
      "客户端提取本地表示并观察域偏移",
      "服务器与客户端在表示空间进行对齐",
      "通过双向交互减小域间差异",
      "使用修正后的表示继续本地训练",
      "聚合后得到泛化更强的共享表征"
    ],
    "applications": "当联邦参与方来自不同医院、不同摄像头或不同地理区域时，FedDBE 这类域偏置消除方法很有价值。它适合跨域视觉、医疗影像与表征迁移任务。",
    "limitations": "表示对齐通常需要更细的特征级设计，训练成本和实现复杂度都高于简单加权平均。若域差异极大且语义空间本身不一致，对齐过程可能变得不稳定甚至带来负迁移。"
  },
  {
    "id": "fedtp",
    "short": "FedTP",
    "title": "FedTP: Federated Learning by Transformer Personalization",
    "year": 2024,
    "first_author": "Hongxia Li",
    "venue": "IEEE TNNLS 2024",
    "idea": "保留客户端个性化自注意力，通过超网络学习客户端特定的注意力投影矩阵。",
    "categories": [
      "personalization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\FedTP.pdf",
    "innovation": "FedTP 针对 Transformer 在联邦场景下的特殊性提出个性化方案：论文观察到简单的 FedAvg 会破坏 self-attention 的个体适配能力，因此把注意力投影矩阵视为需要个性化建模的关键部分。进一步地，它没有停留在‘每个客户端各存一套注意力层’，而是用服务器端超网络来生成客户端特定注意力参数，兼顾个性化、可扩展性与协作共享。",
    "flow_steps": [
      "拆分 Transformer 中共享参数与个性化注意力部分",
      "客户端在本地更新任务参数",
      "服务器训练超网络生成客户专属 Q/K/V 投影",
      "客户端接收生成的个性化注意力矩阵继续训练",
      "最终形成共享骨架 + 专属注意力的联邦模型"
    ],
    "applications": "FedTP 对文本、时序和多模态任务特别有启发，因为这些任务往往高度依赖注意力机制。它也代表了联邦学习与 Transformer 深度融合的一条清晰方向。",
    "limitations": "Transformer 参数规模大、结构复杂，超网络又引入额外模块，因此训练和调参成本较高。若基础任务规模不大，复杂个性化机制带来的收益未必能覆盖额外开销。"
  },
  {
    "id": "fedmc",
    "short": "FedMC",
    "title": "FedMC: Federated Manifold Calibration",
    "year": 2026,
    "first_author": "Yanbiao Ma",
    "venue": "ICLR 2026",
    "idea": "学习客户端局部非线性流形，并用全局几何字典做上下文感知的流形校准。",
    "categories": [
      "personalization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedMC_Federated_Manifold_.pdf",
    "innovation": "FedMC 直接挑战了许多统计校准方法默认采用的全局线性假设。它指出真实联邦数据往往分布在局部非线性流形上，若仍用线性统计做校准，容易生成离流形的伪样本并误导训练。为此，论文通过客户端局部 kernel PCA 学习几何结构，在服务器端构建几何字典，再把这些几何知识回流到客户端，完成更贴近数据结构的校准。",
    "flow_steps": [
      "客户端用 kernel PCA 学习局部几何",
      "服务器聚合形成全局几何字典",
      "几何字典下发给客户端",
      "客户端执行上下文感知的流形内校准",
      "校准结果用于增强任意联邦基线训练"
    ],
    "applications": "FedMC 适合图像、医疗和复杂感知任务，因为这些数据常常具有明显的非线性流形结构。它最大的价值在于可以作为插件增强多种现有联邦方法，而不必重写整个训练框架。",
    "limitations": "局部流形建模本身计算更重，也更依赖特征空间质量。若客户端样本过少或流形估计不稳定，几何字典可能变得嘈杂，进而影响校准效果。"
  },
  {
    "id": "fedaga",
    "short": "FedAGA",
    "title": "FedAGA: A Federated Learning Framework for Enhanced Inter-Client Relationship Learning",
    "year": 2024,
    "first_author": "Jiaqi Ge",
    "venue": "Knowledge-Based Systems 2024",
    "idea": "用动态图建模客户端之间的关系，以图聚合代替简单欧氏空间平均。",
    "categories": [
      "personalization",
      "graph"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\图联邦学习\\FedAga.pdf",
    "innovation": "FedAGA 的思路是把“客户端之间到底像不像”这个问题显式建成一张图，而不是默认所有参与方都应被同等平均。论文通过累计梯度相似性构建动态图拓扑，并从收敛性与差异性两个角度筛选更可靠的关系边，让聚合过程真正受客户端关系结构驱动。",
    "flow_steps": [
      "收集各客户端训练过程中的表示或梯度信息",
      "计算客户端间相似性并构图",
      "根据收敛/分歧准则修正边权",
      "在图结构上执行关系感知聚合",
      "将个性化模型回传客户端继续训练"
    ],
    "applications": "FedAGA 适合医疗机构、区域设备群、物联网子网络等天然存在群体关系的场景。它能把“谁更应该互相学习”这一问题做得更细致，因此在个性化联邦中很有代表性。",
    "limitations": "构图和关系更新本身会增加计算与通信开销，且对相似性度量较敏感。若关系图估计错误，模型会把不该共享的知识强行连在一起，反而损伤性能。"
  },
  {
    "id": "perfedgt",
    "short": "PerFedGT",
    "title": "PerFedGT: A Personalized Federated Graph Transformer for Scale-Heterogeneous Graph Data",
    "year": 2024,
    "first_author": "Haohe Jia",
    "venue": "Information Processing & Management 2024",
    "idea": "面向尺度异构图数据，用个性化图 Transformer 处理跨机构图规模差异。",
    "categories": [
      "personalization",
      "graph"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\PerFedGT.pdf",
    "innovation": "PerFedGT 针对图联邦中很实际但常被忽略的“规模异构”问题，即不同客户端的图规模、子图稀疏度和结构复杂度差异巨大。论文把图 Transformer 与个性化联邦结合起来，使模型既能共享图级全局知识，又能根据各客户端图的尺度特点保留专属适配能力。",
    "flow_steps": [
      "客户端构建各自图或子图表示",
      "图 Transformer 在本地建模结构依赖",
      "共享部分上传聚合，个性化部分本地保留",
      "服务器更新共享图表示能力",
      "客户端继续基于本地图规模做适配"
    ],
    "applications": "该方法非常适合金融反欺诈、推荐、社交关系分析和生物分子网络等图任务，尤其是参与方拥有不同规模和稀疏度图数据时。",
    "limitations": "图 Transformer 本身计算代价高，对大图和稀疏图的训练较重；再叠加联邦与个性化机制后，整体系统复杂度会明显提升。"
  },
  {
    "id": "fd",
    "short": "FD",
    "title": "Communication-Efficient On-Device Machine Learning: Federated Distillation and Augmentation under Non-IID Private Data",
    "year": 2019,
    "first_author": "Eunjeong Jeong",
    "venue": "Workshop / Preprint 2019",
    "idea": "用类别级 logits 蒸馏代替整模型同步，并结合联邦数据增强缓解 non-IID。",
    "categories": [
      "distillation"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FD.pdf",
    "innovation": "FD 的开创性在于它很早就意识到参数同步并不是联邦协作的唯一方式。论文直接交换类别平均 logits 这类轻量知识，再辅以 federated augmentation 让各客户端用共享生成能力补齐类别分布，从而同时减少通信量和缓解类别不平衡。",
    "flow_steps": [
      "客户端本地训练模型",
      "按类别统计软预测或 logits 知识",
      "服务器聚合类别级知识并广播",
      "客户端利用蒸馏目标继续训练",
      "配合数据增强模块缓解类别偏移"
    ],
    "applications": "FD 适合模型很大、带宽紧张、终端设备资源有限的场景，也适合作为后续蒸馏式联邦与模型异构联邦的思想起点。",
    "limitations": "类别级统计虽然轻量，但表达能力有限，难以承载更复杂的中间表示知识。若标签空间不一致或类别分布极端稀疏，蒸馏信号会明显变弱。"
  },
  {
    "id": "fedkd",
    "short": "FedKD",
    "title": "Communication-Efficient Federated Learning via Knowledge Distillation",
    "year": 2024,
    "first_author": "Chuhan Wu",
    "venue": "Nature Communications 2024",
    "idea": "结合双向知识蒸馏与动态梯度压缩，同时追求通信高效与性能稳定。",
    "categories": [
      "distillation"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedKD.pdf",
    "innovation": "FedKD 不只是把蒸馏当成一个辅助损失，而是把它与通信压缩联合设计。论文利用 teacher-student 双向蒸馏提升表征迁移，同时结合动态梯度压缩显著削减上传量，使‘蒸馏’和‘通信效率’不再是两条割裂路线，而是同一个系统目标下的协同部件。",
    "flow_steps": [
      "客户端维护 teacher/student 或双模型结构",
      "本地训练时执行互蒸馏",
      "上传压缩后的梯度或关键更新",
      "服务器聚合并回传共享知识",
      "客户端继续在蒸馏约束下迭代"
    ],
    "applications": "FedKD 面向需要隐私保护但又不能承受高通信成本的真实应用，如医疗、广告和智能终端。它对于大模型或深网络联邦尤其有吸引力。",
    "limitations": "互蒸馏和压缩策略同时存在时，系统调优复杂度较高。若压缩过强或 teacher/student 能力差异处理不好，蒸馏收益可能被压缩误差抵消。"
  },
  {
    "id": "fedgkd",
    "short": "FedGKD",
    "title": "FedGKD: Toward Heterogeneous Federated Learning via Global Knowledge Distillation",
    "year": 2024,
    "first_author": "Dezhong Yao",
    "venue": "IEEE Transactions on Computers 2024",
    "idea": "通过全局知识蒸馏在异构模型之间共享高层语义，不依赖同构参数空间。",
    "categories": [
      "distillation"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedGKD_Toward_Heterogeneous_Federated_Learning_via_Global_Knowledge_Distillation.pdf",
    "innovation": "FedGKD 把异构联邦中的共享对象从参数转成全局超知识。客户端先提炼高层表征和软预测，服务器再将这些知识融合后回流给不同架构的客户端。这样即使模型结构不同，也能在语义层进行协作，而不再被参数维度对齐所束缚。",
    "flow_steps": [
      "不同架构客户端本地训练各自模型",
      "提取表征与软标签等 hyper-knowledge",
      "服务器汇聚全局知识",
      "回传给异构客户端执行蒸馏",
      "完成跨架构协同更新"
    ],
    "applications": "FedGKD 很适合设备能力差异明显、无法要求统一模型架构的边缘环境。它也是 heterogeneous FL 里非常典型的蒸馏式解决方案。",
    "limitations": "语义层共享需要一个好的知识接口，否则不同模型的特征表达很难真正对齐。蒸馏过程还可能带来额外的训练时间和知识损失。"
  },
  {
    "id": "fedd2s",
    "short": "FedD2S",
    "title": "FedD2S: Personalized Data-Free Federated Knowledge Distillation",
    "year": 2024,
    "first_author": "Kawa Atapour",
    "venue": "arXiv 2024",
    "idea": "在无数据蒸馏框架下用 deep-to-shallow 层丢弃增强个性化。",
    "categories": [
      "distillation",
      "personalization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\2402.10846v1.pdf",
    "innovation": "FedD2S 把 data-free knowledge distillation 与个性化联邦结合起来，重点解决无公共数据条件下如何蒸馏和如何避免统一蒸馏抹平个体差异。它提出 deep-to-shallow 的层级丢弃机制，使蒸馏过程更关注对个体有用的知识层次，而不是一股脑追求全局一致。",
    "flow_steps": [
      "客户端训练本地模型并上传必要知识",
      "服务器在无真实数据条件下组织蒸馏",
      "采用 deep-to-shallow 层级丢弃控制知识注入",
      "客户端接收蒸馏结果继续个性化训练",
      "多轮迭代形成兼顾公平性和个体性的模型"
    ],
    "applications": "FedD2S 适用于数据极度敏感、无法提供公共代理数据的个性化场景，例如医疗或隐私法规严格的行业协作。它也适合研究 data-free FL 的路线演化。",
    "limitations": "无数据蒸馏天然更依赖生成假设和知识替代机制，若蒸馏信号不足，效果会明显波动。层级丢弃策略也引入新的结构型超参数。"
  },
  {
    "id": "fedntd",
    "short": "FedNTD",
    "title": "Preservation of the Global Knowledge by Not-True Distillation in Federated Learning",
    "year": 2022,
    "first_author": "Gihun Lee",
    "venue": "ICML 2022",
    "idea": "只对非真实类别做蒸馏，减少遗忘并保留全局模型的暗知识。",
    "categories": [
      "distillation",
      "personalization"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedNTD.pdf",
    "innovation": "FedNTD 很巧妙地观察到，在联邦学习中真正容易被遗忘的往往不是正确类别，而是那些反映全局判别结构的“非真类概率分布”。因此它只蒸馏 not-true classes，把保留暗知识这件事做得更聚焦，既减轻本地分布过拟合，又避免把蒸馏目标设计得过于笼统。",
    "flow_steps": [
      "服务器下发全局模型",
      "客户端本地计算监督损失",
      "额外对非真实类别概率做蒸馏约束",
      "上传更新并聚合全局模型",
      "多轮训练中持续抑制遗忘"
    ],
    "applications": "FedNTD 适合分类任务，尤其是在类别分布偏斜、局部训练容易遗忘全局决策边界的场景。它实现相对轻量，却能明显提升异构条件下的全局与本地表现。",
    "limitations": "该方法主要针对分类设置，且依赖 soft label 中隐含的暗知识质量。若类别非常多或预测分布本身噪声较大，not-true 蒸馏信号也可能失真。"
  },
  {
    "id": "fedproto",
    "short": "FedProto",
    "title": "FedProto: Federated Prototype Learning across Heterogeneous Clients",
    "year": 2022,
    "first_author": "Yue Tan",
    "venue": "AAAI 2022",
    "idea": "交换类别原型而不是梯度，在原型空间实现跨客户端知识共享。",
    "categories": [
      "distillation"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedProto.pdf",
    "innovation": "FedProto 把联邦共享对象从参数/梯度转成类别原型，这是一种非常自然的语义级蒸馏。原型聚合比梯度聚合更不依赖模型结构细节，也更能直接表达类别中心语义，因此对于模型异构、输入异构和训练步长差异都更宽容。",
    "flow_steps": [
      "客户端提取各类别原型特征",
      "服务器聚合得到全局类别原型",
      "全局原型广播回客户端",
      "客户端用原型约束本地表示学习",
      "持续迭代优化局部与全局语义一致性"
    ],
    "applications": "FedProto 适合视觉分类、医学影像分类和多模态分类等任务，也适合 heterogeneous FL 场景。它是很多原型式联邦工作的出发点。",
    "limitations": "原型对类别定义和特征质量高度敏感。若类别本身内部多样性很强，单个原型很难完整表达语义，可能导致过度简化。"
  },
  {
    "id": "fedgmkd",
    "short": "FedGMKD",
    "title": "FedGMKD: An Efficient Prototype Federated Learning Framework through Knowledge Distillation and Discrepancy-Aware Aggregation",
    "year": 2024,
    "first_author": "Jianqiao Zhang",
    "venue": "Preprint 2024",
    "idea": "结合原型蒸馏、GMM 原型融合和差异感知聚合，提升个性化与全局泛化。",
    "categories": [
      "distillation"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\图联邦学习\\FedGMKD.pdf",
    "innovation": "FedGMKD 将原型学习、知识蒸馏和聚合加权三件事放到一个统一框架里。它先在客户端通过高斯混合模型构造更细粒度的原型特征，再把这些原型及其软预测用于蒸馏，最后通过 discrepancy-aware aggregation 根据数据质量与数量调节贡献权重，形成更稳健的个性化联邦协同。",
    "flow_steps": [
      "客户端训练本地模型并拟合原型分布",
      "利用 GMM 生成更丰富的原型特征",
      "执行原型蒸馏得到软知识",
      "服务器依据差异度做加权聚合",
      "将融合结果反馈到下一轮本地训练"
    ],
    "applications": "FedGMKD 适合数据异构显著、且希望同时提升局部与全局性能的分类任务。它也展示了原型蒸馏路线如何向更精细的概率建模延伸。",
    "limitations": "多模块叠加意味着训练链路更长，对原型质量、GMM 拟合和加权策略都较敏感。若数据量小，原型统计可能不稳定。"
  },
  {
    "id": "fedfree",
    "short": "FedFree",
    "title": "FedFree: Breaking Knowledge-Sharing Barriers through Layer-Wise Alignment in Heterogeneous Federated Learning",
    "year": 2024,
    "first_author": "Haizhou Du",
    "venue": "Preprint 2024",
    "idea": "提出无代理数据、无统一模型的分层对齐蒸馏机制，打通异构模型知识共享。",
    "categories": [
      "distillation"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedFree_Breaking_Knowled.pdf",
    "innovation": "FedFree 直面 heterogeneous FL 中两个常见障碍：需要公共代理数据，以及知识传递过于粗粒度。它通过 reverse layer-wise knowledge transfer 和层级对齐，在不依赖公共数据、也不强制同构模型的情况下，尽量保留不同网络中的细粒度知识。",
    "flow_steps": [
      "各异构客户端独立训练本地模型",
      "提取不同层级的中间知识",
      "服务器组织跨层对齐与反向知识迁移",
      "客户端接收对齐信号继续训练",
      "逐层打通异构模型间知识共享"
    ],
    "applications": "FedFree 适用于移动设备、边缘摄像头等模型架构不统一的场景，对隐私和代理数据受限的任务尤其有意义。",
    "limitations": "逐层对齐需要设计层间映射关系，工程上并不轻。模型差异越大，对齐越难，层级知识未必总能可靠地互相翻译。"
  },
  {
    "id": "fedgh",
    "short": "FedGH",
    "title": "FedGH: Heterogeneous Federated Learning with Generalized Global Header",
    "year": 2023,
    "first_author": "Liping Yi",
    "venue": "Preprint 2023",
    "idea": "通过广义全局头部在不同骨干网络间共享更稳定的分类语义。",
    "categories": [
      "distillation"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\个性化联邦学习\\FedGH.pdf",
    "innovation": "FedGH 认为在 heterogeneous FL 里，真正适合共享的未必是整张网络，而可能是更贴近任务语义的 header。它通过 generalized global header 将不同模型的高层判别知识收束到一个可共享接口，让多样化骨干网络仍能围绕一致的判别头进行协作。",
    "flow_steps": [
      "客户端使用各自异构骨干提取特征",
      "引入广义全局 header 作为共享接口",
      "服务器聚合并更新 header 语义",
      "客户端结合本地骨干继续训练",
      "实现异构网络之间的高层协同"
    ],
    "applications": "FedGH 适合分类任务及资源差异明显的终端部署，因为不同客户端可以保留各自骨干规模与结构，只在高层语义接口上统一。",
    "limitations": "如果不同骨干提取到的特征空间差异过大，仅靠共享 header 未必足以充分对齐。方法更适合高层语义相近的任务，不一定覆盖复杂生成任务。"
  },
  {
    "id": "feddiff",
    "short": "FedDiff",
    "title": "Navigating Heterogeneity and Privacy in One-Shot Federated Learning with Diffusion Models",
    "year": 2024,
    "first_author": "Matías Mendieta",
    "venue": "WACV 2024",
    "idea": "用扩散模型支持 one-shot 联邦，并在差分隐私下用频域过滤提升伪样本质量。",
    "categories": [
      "generative"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\FedDiff.pdf",
    "innovation": "FedDiff 将扩散模型引入 one-shot federated learning，让客户端只通信一次仍能通过生成模型弥补统计异构。它不仅验证了扩散模型能承担样本合成角色，还在差分隐私设置下提出 Fourier Magnitude Filtering 来改善生成样本质量，使隐私保护与可训练性之间的冲突得到缓和。",
    "flow_steps": [
      "客户端本地训练或适配扩散模型",
      "单次向服务器上传必要模型知识",
      "服务器利用生成能力合成全局训练数据",
      "在差分隐私场景下用 FMF 过滤频域噪声",
      "基于生成样本训练全局模型"
    ],
    "applications": "FedDiff 适合通信极其受限或不方便频繁同步的场景，也适合研究联邦生成模型在 one-shot 协同中的潜力。",
    "limitations": "扩散模型训练本身代价高，单次通信虽然节省带宽，却把很多难点转移到了生成质量上。若生成数据分布失真，全局模型会被系统性误导。"
  },
  {
    "id": "feddm",
    "short": "FedDDPM",
    "title": "Training Diffusion Models with Federated Learning",
    "year": 2024,
    "first_author": "Matthijs de Goede",
    "venue": "Preprint 2024",
    "idea": "直接在联邦场景训练 DDPM，并利用 UNet 结构削减参数交换量。",
    "categories": [
      "generative"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\Training_Diffusion_Models_with_Federated_Learning.pdf",
    "innovation": "这篇论文的亮点在于不是用生成模型辅助联邦，而是把联邦学习本身用于训练扩散生成模型。作者针对 DDPM 的 UNet 骨干设计了更节省通信的交换方式，大幅减少需要同步的参数量，同时尽量保持生成质量不输集中式训练。",
    "flow_steps": [
      "客户端持有本地私有图像数据",
      "在本地训练扩散模型的 UNet 组件",
      "仅同步关键参数子集而非整模型",
      "服务器执行联邦聚合更新全局扩散模型",
      "反复迭代直至生成质量稳定"
    ],
    "applications": "适用于多机构联合训练隐私敏感生成模型，例如医疗图像生成、企业间版权敏感内容生成或去中心化创作平台。",
    "limitations": "生成模型的参数体量和训练时长都远高于常规分类模型，即使做了裁剪，整体代价仍高。不同客户端数据风格差异大时，生成质量很容易被拉扯。"
  },
  {
    "id": "promptfl",
    "short": "PromptFL",
    "title": "PromptFL: Let Federated Participants Cooperatively Learn Prompts Instead of Models",
    "year": 2024,
    "first_author": "Tao Guo",
    "venue": "IEEE Transactions on Mobile Computing 2024",
    "idea": "联邦参与方不再训练整模型，而是协同优化基础模型上的软提示。",
    "categories": [
      "prompt"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\联邦提示学习\\PromptFL_Let_Federated_Participants_Cooperatively_Learn_Prompts_Instead_of_Models__Federated_Learning_in_Age_of_Foundation_Model.pdf",
    "innovation": "PromptFL 的范式转换非常明确：在基础模型时代，真正需要联邦优化的可能只是少量软提示，而不是整个大模型。它借助 CLIP 等现成基础模型，把各客户端的协作目标压缩到轻量提示向量上，从而显著降低训练与通信成本，同时借用基础模型预训练知识弥补本地数据不足。",
    "flow_steps": [
      "服务器下发冻结的基础模型及初始提示",
      "客户端只在本地更新软提示参数",
      "上传提示更新而非完整模型参数",
      "服务器聚合得到共享提示",
      "聚合后的提示继续回传客户端迭代"
    ],
    "applications": "PromptFL 特别适合少样本、弱算力和带宽敏感的边缘终端任务，也适合跨机构快速迁移视觉语言模型能力。",
    "limitations": "提示学习高度依赖基础模型先验。如果目标任务与预训练语义差距过大，单靠提示可能不足以充分适配，仍需要更重的微调机制。"
  },
  {
    "id": "dtfl",
    "short": "DT-FL",
    "title": "Digital Twin-Assisted Federated Learning Service Provisioning Over Mobile Edge Networks",
    "year": 2024,
    "first_author": "Ruirui Zhang",
    "venue": "IEEE Transactions on Computers 2024",
    "idea": "利用数字孪生建模网络与资源动态，联动调度多 FL 服务和带宽分配。",
    "categories": [
      "system"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\Digital_Twin-Assisted_Federated_Learning_Service_Provisioning_Over_Mobile_Edge_Networks.pdf",
    "innovation": "这篇论文把数字孪生引入联邦学习服务编排，真正关注的是多服务、移动用户和动态带宽环境中的系统调度问题。它不仅在离线场景下给出启发式和近似算法，还在在线条件下利用历史带宽数据和强化学习做动态分配，体现出算法与系统协同优化的特点。",
    "flow_steps": [
      "在 MEC 环境中为用户和资源建立数字孪生",
      "根据服务请求建模多 FL 任务竞争",
      "执行离线或在线的设备/带宽分配",
      "调用强化学习策略自适应调整资源",
      "最大化整体联邦服务效用"
    ],
    "applications": "适合移动边缘计算、车联网、工业物联网等需要同时承载多个联邦任务的部署场景。它对联邦平台建设而非单一模型精度更有指导意义。",
    "limitations": "系统建模假设较多，对孪生质量和带宽预测依赖强。若真实环境变化过快或观测不足，调度优势可能明显下降。"
  },
  {
    "id": "fairness_survey_2026",
    "short": "Fairness Survey",
    "title": "A Survey on Group Fairness in Federated Learning: Challenges, Taxonomy of Solutions and Directions for Future Research",
    "year": 2026,
    "first_author": "Teresa Salazar",
    "venue": "Artificial Intelligence Review 2026",
    "idea": "系统梳理联邦学习中的群体公平问题、解决路径与未来研究方向。",
    "categories": [
      "survey"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\综述类文章\\A Survey on Group Fairness in Federated Learning.pdf",
    "innovation": "这篇综述的重要性不在于提出新算法，而在于把 FL 群体公平问题系统化。它不仅总结了已有方法，还从数据划分、偏差来源、敏感属性处理和评测实践等角度提出新的分类框架，使公平性从零散议题变成一条可以被结构化研究的路线。",
    "flow_steps": [
      "界定联邦学习中的公平性问题",
      "梳理不同偏差来源与敏感属性设置",
      "对已有方法进行分层分类",
      "总结数据集、指标与应用场景",
      "提出未来开放问题与研究方向"
    ],
    "applications": "适合做开题综述、论文相关工作与公平性研究的知识框架搭建，也适合为算法设计寻找评价标准和研究空白。",
    "limitations": "综述类论文不能替代具体方法验证，且公平性的定义往往依赖场景，实际应用中仍需根据任务目标重新选择指标与约束。"
  },
  {
    "id": "fairness_frontier",
    "short": "FL Fairness",
    "title": "Federated Learning at the Forefront of Fairness: A Multifaceted Perspective",
    "year": 2024,
    "first_author": "Noorain Mukhtiar",
    "venue": "Survey / Preprint 2024",
    "idea": "从性能公平与能力公平双重视角归纳公平联邦的技术谱系和评价指标。",
    "categories": [
      "survey"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\综述类文章\\Federated-Learning-at-the-Forefront-of-Fairness.pdf",
    "innovation": "这篇综述的特色在于强调公平并不是单一指标，而是包含性能导向公平和能力导向公平两条主线。它让研究者看到，在联邦学习中，被忽视的不只是模型偏差，还包括客户端资源差异、参与机会差异和贡献回报差异。",
    "flow_steps": [
      "定义公平关注维度",
      "按多面向视角归纳已有方法",
      "总结常用公平性指标",
      "分析公平与性能之间的张力",
      "提出未来研究问题"
    ],
    "applications": "适合在写综述、设计公平性实验或构造评价体系时作为上位参考。它对于理解客户端能力差异引发的不公平尤其有帮助。",
    "limitations": "由于覆盖面广，具体方法细节不会展开到实现层。对实际项目而言，需要与具体公平优化算法配套阅读。"
  },
  {
    "id": "kd_foundation",
    "short": "KD",
    "title": "Distilling the Knowledge in a Neural Network",
    "year": 2015,
    "first_author": "Geoffrey Hinton",
    "venue": "arXiv 2015",
    "idea": "奠定现代知识蒸馏基础，用软目标把大模型或集成模型的暗知识传给小模型。",
    "categories": [
      "survey"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\知识蒸馏.pdf",
    "innovation": "这篇论文是后续所有蒸馏式联邦方法的重要理论源头。它指出软标签中包含比硬标签更丰富的类间关系信息，因此模型压缩并不只是减少参数，而是让学生模型继承教师模型的判别结构与暗知识。",
    "flow_steps": [
      "训练性能更强的教师模型或模型集成",
      "生成带温度的软目标分布",
      "学生模型同时拟合硬标签与软目标",
      "在更小计算预算下保留教师知识",
      "完成模型压缩或迁移"
    ],
    "applications": "虽然不是联邦学习论文，但它直接支撑了 FD、FedKD、FedGKD、FedNTD 等多条联邦蒸馏路线，因此适合作为技术路线图中的背景理论节点。",
    "limitations": "原始蒸馏框架建立在集中式监督学习语境下，没有直接考虑多客户端异构、隐私和通信约束，因此迁移到联邦场景时需要额外设计。"
  },
  {
    "id": "comm",
    "short": "CoMM",
    "title": "What to Align in Multimodal Contrastive Learning?",
    "year": 2025,
    "first_author": "Benoit Dufumier",
    "venue": "ICLR 2025",
    "idea": "提出 CoMM，从共享、互补与独特信息角度重新思考多模态对齐。",
    "categories": [
      "survey"
    ],
    "source_path": "C:\\Users\\48174\\Desktop\\联邦学习\\综述类文章\\ICLR-2025-what-to-align-in-multimodal-contrastive-learning-Paper-Conference.pdf",
    "innovation": "这篇论文虽然不属于联邦学习，但它对“应该对齐什么信息”给出了很好的视角，能够为模型对比学习、表征对齐和跨客户端知识融合提供启发。它强调多模态学习不应只盯着共享冗余信息，还要显式建模互补和独有信息，这与个性化联邦中的共享-私有拆分思路存在呼应。",
    "flow_steps": [
      "构造多模态表示",
      "在单一多模态空间中最大化互信息",
      "分离共享、协同和独有信息成分",
      "基于新目标优化对比学习过程",
      "评估不同模态交互质量"
    ],
    "applications": "可作为理解对比式表征对齐、个性化共享边界以及未来多模态联邦学习设计的背景参考。",
    "limitations": "它不是联邦论文，因此在通信、聚合和隐私问题上没有直接答案；更多是提供表征学习层面的启发。"
  }
];

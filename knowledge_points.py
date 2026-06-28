# -*- coding: utf-8 -*-
"""
Electron microscopy knowledge points organized by difficulty and category.
Used for the daily check-in study feature.
"""

KNOWLEDGE_POINTS = [
    # ===== Beginner (初级) =====
    {
        "title": "电子显微镜的基本原理",
        "content": "电子显微镜利用高速电子束代替光束照射样品，通过电磁透镜聚焦成像。由于电子的德布罗意波长远小于可见光，电镜的分辨率远高于光学显微镜，可达亚纳米级别。",
        "difficulty": "beginner",
        "category": "基础概念"
    },
    {
        "title": "SEM vs TEM",
        "content": "扫描电子显微镜(SEM)通过聚焦电子束在样品表面扫描，检测二次电子或背散射电子信号成像，主要用于观察表面形貌。透射电子显微镜(TEM)则让电子束穿透薄样品，检测透射电子成像，可观察内部结构。",
        "difficulty": "beginner",
        "category": "基础概念"
    },
    {
        "title": "电磁透镜",
        "content": "电磁透镜是电镜的核心组件，通过通电线圈产生的磁场对电子束进行汇聚和聚焦。改变线圈电流可以调节透镜焦距。常见的电磁透镜包括聚光镜、物镜和投影镜。",
        "difficulty": "beginner",
        "category": "基础概念"
    },
    {
        "title": "样品制备的重要性",
        "content": "电镜样品制备直接影响成像质量。SEM样品需导电、干燥、固定；TEM样品需极薄(通常<100nm)。常用制备技术包括：临界点干燥、离子减薄、聚焦离子束(FIB)切割、超薄切片等。",
        "difficulty": "beginner",
        "category": "实验技术"
    },
    {
        "title": "电子束与样品的相互作用",
        "content": "高能电子束入射样品后产生多种信号：二次电子(SE)、背散射电子(BSE)、特征X射线、俄歇电子、阴极发光等。不同信号携带不同信息，用于不同分析模式。",
        "difficulty": "beginner",
        "category": "基础概念"
    },

    # ===== Intermediate (中级) =====
    {
        "title": "高分辨TEM (HRTEM) 成像原理",
        "content": "HRTEM利用相位衬度成像，当电子束通过晶体样品时发生布拉格衍射，透射束与衍射束干涉形成晶格条纹像。HRTEM可直接观察原子排列，分辨晶面间距，是材料科学的重要表征手段。",
        "difficulty": "intermediate",
        "category": "成像技术"
    },
    {
        "title": "选区电子衍射 (SAED)",
        "content": "SAED通过在物镜像平面插入选区光阑，选择样品微区(亚微米级)进行电子衍射分析。获得的衍射花样可用于确定晶体结构、取向关系和物相鉴定。结合HRTEM可实现结构-形貌关联分析。",
        "difficulty": "intermediate",
        "category": "衍射分析"
    },
    {
        "title": "EDS能谱分析原理",
        "content": "能量色散X射线光谱(EDS)利用电子束激发样品产生特征X射线，通过半导体探测器(Si(Li)或SDD)分析X射线能量分布，实现元素定性定量分析。轻元素检测受限，重元素灵敏度高。",
        "difficulty": "intermediate",
        "category": "成分分析"
    },
    {
        "title": "背散射电子衍射 (EBSD)",
        "content": "EBSD通过分析SEM中倾斜样品产生的背散射电子衍射菊池带花样，获取晶体取向、织构、晶界类型等信息。空间分辨率可达数十纳米，是材料微观组织表征的重要工具。",
        "difficulty": "intermediate",
        "category": "衍射分析"
    },
    {
        "title": "扫描透射电镜 (STEM)",
        "content": "STEM结合SEM和TEM原理，将聚焦电子束在样品上逐点扫描，用环形探测器收集透射电子信号。高角环形暗场(HAADF)-STEM像的原子序数衬度(Z-衬度)可直接对原子列成像。",
        "difficulty": "intermediate",
        "category": "成像技术"
    },
    {
        "title": "电子能量损失谱 (EELS)",
        "content": "EELS分析穿过薄样品的电子能量损失分布。低损失区(<50eV)包含等离激元信息，核心损失区(>50eV)反映元素电子壳层激发。EELS可检测轻元素和化学键状态，空间分辨率可达原子级。",
        "difficulty": "intermediate",
        "category": "成分分析"
    },

    # ===== Advanced (高级) =====
    {
        "title": "球差校正技术",
        "content": "传统电磁透镜的球差是限制分辨率的主要因素。球差校正器使用多级四极-八极透镜组合产生负球差，抵消物镜的正球差。球差校正TEM/STEM可实现亚埃级(0.05nm以下)分辨率，直接观察单个原子和化学键。",
        "difficulty": "advanced",
        "category": "成像技术"
    },
    {
        "title": "原位电镜技术",
        "content": "原位TEM/SEM在观察过程中实时操控样品环境，如加热(原位加热台至1500°C)、冷却、气体反应、液体环境、力学加载或电场/磁场施加。可动态观察相变、催化反应、纳米材料生长等过程。",
        "difficulty": "advanced",
        "category": "前沿技术"
    },
    {
        "title": "电子断层三维重构",
        "content": "电子断层成像(ET)通过倾转样品(-70°到+70°)，在不同角度采集投影图像，再通过加权背投影或迭代算法重构三维结构。分辨率可达1-2nm，广泛用于细胞生物学和材料科学的3D分析。",
        "difficulty": "advanced",
        "category": "前沿技术"
    },
    {
        "title": "4D-STEM 技术",
        "content": "4D-STEM使用像素化探测器在每个扫描位置记录完整的二维衍射花样，形成四维数据集(2D空间×2D动量空间)。通过后处理可同时重构出虚拟暗场像、应变分布、极化场和晶体取向图。",
        "difficulty": "advanced",
        "category": "前沿技术"
    },
    {
        "title": "低压电镜与环境电镜",
        "content": "环境扫描电镜(ESEM)允许在低真空或气体环境下成像，可观察含水或非导电样品。低压SEM(1-5kV)减少电子束损伤和荷电效应，提高表面灵敏度，适合表面敏感的有机和生物样品。",
        "difficulty": "advanced",
        "category": "前沿技术"
    },
    {
        "title": "冷冻电镜 (Cryo-EM)",
        "content": "冷冻电镜将生物样品快速冷冻在玻璃态冰中，在液氮温度下观察。单颗粒分析技术可解析生物大分子的近原子分辨率三维结构。2017年诺贝尔化学奖授予Cryo-EM的发展者。",
        "difficulty": "advanced",
        "category": "前沿技术"
    },
    {
        "title": "像差校正与图像模拟",
        "content": "定量HRTEM分析需通过多片层法模拟电子束与样品的相互作用。软件如QSTEM、DrSTEM基于密度泛函理论计算散射势，模拟不同条件下的图像，并与实验图像对比确定原子结构。",
        "difficulty": "advanced",
        "category": "理论计算"
    },
    {
        "title": "电子全息术",
        "content": "电子全息术利用场发射枪的相干电子束，将物波与参考波干涉记录全息图。通过重建可定量测量样品内部的电势分布、磁场分布和厚度变化，空间分辨率达纳米级。",
        "difficulty": "advanced",
        "category": "前沿技术"
    },
]


def get_points_by_difficulty(difficulty):
    """Get knowledge points filtered by difficulty level."""
    return [p for p in KNOWLEDGE_POINTS if p["difficulty"] == difficulty]


def get_today_point(day_of_week=None):
    """Get a knowledge point for today's study.
    If day_of_week is provided (0=Mon..6=Sun), tries to return a matching point.
    """
    import random
    if day_of_week is not None:
        themed = [p for p in KNOWLEDGE_POINTS if p.get("day_of_week") == day_of_week]
        if themed:
            return random.choice(themed)
    return random.choice(KNOWLEDGE_POINTS)


DIFFICULTY_LABELS = {
    "beginner": "初级",
    "intermediate": "中级",
    "advanced": "高级",
}

DIFFICULTY_COLORS = {
    "beginner": "#10b981",
    "intermediate": "#f59e0b",
    "advanced": "#ef4444",
}

CATEGORIES = list(set(p["category"] for p in KNOWLEDGE_POINTS))
CATEGORIES.sort()

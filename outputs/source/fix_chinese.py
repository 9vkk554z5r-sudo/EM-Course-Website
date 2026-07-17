# -*- coding: utf-8 -*-
import os

templates_dir = r"C:\Users\hp\Documents\Codex\2026-06-24\agent-agent-python-1-2-9\electron-microscopy-course\templates"

nav_labels = ["管理", "首页", "每日学习", "实验视频", "文献中心", "上传文献", "文献星云", "小森林", "个人中心"]

path = os.path.join(templates_dir, "base.html")
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

label_idx = 0
for i in range(len(lines)):
    s = lines[i].strip()
    if s == "??" or s == "????" or s == "?????" or s == "???":
        lines[i] = lines[i].replace(s, nav_labels[label_idx])
        label_idx += 1

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"base.html: fixed {label_idx} nav labels")

# Fix admin templates
admin_fixes = {
    "admin_base.html": [("管理后台", "管理后台"), ("概览", "概览"), ("知识库", "知识库"), ("实验视频", "实验视频"), ("用户管理", "用户管理"), ("返回前台", "返回前台")],
    "admin_dashboard.html": [("概览", "概览"), ("注册用户", "注册用户"), ("总打卡次数", "总打卡次数"), ("文献总数", "文献总数"), ("实验视频", "实验视频"), ("知识点", "知识点")],
    "admin_knowledge.html": [("知识库管理", "知识库管理"), ("添加知识点", "添加知识点"), ("现有知识点", "现有知识点"), ("知识点标题", "知识点标题"), ("初级", "初级"), ("中级", "中级"), ("高级", "高级"), ("编辑", "编辑"), ("删除", "删除"), ("保存", "保存"), ("取消", "取消"), ("分类", "分类")],
    "admin_videos.html": [("实验视频管理", "实验视频管理"), ("上传新视频", "上传新视频"), ("视频列表", "视频列表"), ("视频标题", "视频标题"), ("视频描述", "视频描述"), ("上传", "上传"), ("删除", "删除")],
    "admin_users.html": [("用户管理", "用户管理"), ("学号", "学号"), ("姓名", "姓名"), ("邮箱", "邮箱"), ("管理员", "管理员"), ("注册时间", "注册时间"), ("操作", "操作"), ("设为管理", "设为管理"), ("取消管理", "取消管理")],
    "protocols.html": [("实验Protocol视频", "实验Protocol视频"), ("全部", "全部"), ("暂无实验视频", "暂无实验视频"), ("初级", "初级"), ("中级", "中级"), ("高级", "高级")],
    "literature_upload.html": [("上传文献", "上传文献"), ("新增文献", "新增文献"), ("我的上传", "我的上传"), ("文献标题", "文献标题"), ("提交并调用Agent获取信息", "提交并调用Agent获取信息"), ("暂无上传记录", "暂无上传记录")],
    "rewards.html": [("我的小森林", "我的小森林"), ("累计种树", "累计种树"), ("周奖励", "周奖励"), ("月奖励", "月奖励"), ("当前连续", "当前连续"), ("最长连续", "最长连续"), ("我的小森林", "我的小森林"), ("周全勤", "周全勤"), ("月全勤", "月全勤"), ("还没有种下小树", "还没有种下小树"), ("开始学习打卡", "开始学习打卡")],
    "dashboard.html": [("小森林", "小森林"), ("查看全部", "查看全部"), ("全勤奖励", "全勤奖励")],
}

for fname, replacements in admin_fixes.items():
    fpath = os.path.join(templates_dir, fname)
    if not os.path.exists(fpath):
        print(f"{fname}: NOT FOUND")
        continue
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    # Since all Chinese was stripped, we need to add it back based on context
    # But the admin templates don't have Chinese text at all right now
    print(f"{fname}: needs complete rewrite ({len(content)} bytes)")

print("Chinese text fix script ready - run it!")
print("Note: admin templates need to be rewritten from scratch")
print("because all Chinese text was completely stripped.")

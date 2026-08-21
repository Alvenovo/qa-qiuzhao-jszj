# 2027届秋招 · 江苏浙江测试岗

只收录**还在招**的软件测试 / 测试开发 / 质量保障等岗位，地区限江苏、浙江。

公司电脑不爬数据。每天中午 12 点（北京时间）由 **GitHub Actions 在云端**更新；家里电脑 `git pull` 即可。

## 家里怎么用

```bash
git clone https://github.com/Alvenovo/qa-qiuzhao-jszj.git
cd qa-qiuzhao-jszj
```

直接打开 `index.html`，或看 GitHub Pages（仓库 Settings → Pages 打开后）。

页面可按江苏/浙江筛选，按**截止时间**、**更新时间**升序或降序排序。

## 每天自动更新

`.github/workflows/daily-update.yml` 会在 UTC 04:00（北京时间 12:00）跑 `python scripts/update.py`：

- 丢掉已经截止的岗位
- 从企业校招官网、公开秋招聚合等来源刷新
- 写回 `jobs.json` 和 `index.html` 并提交

第一次推送后请：仓库 **Actions** 允许工作流，并手动 Run 一次确认。

家里如果要自己补爬（可选）：

```bash
pip install -r requirements.txt
python scripts/update.py
git add jobs.json index.html README.md meta.json
git commit -m "更新招聘数据"
git push
```

不要在仓库里保存 Boss / 智联账号密码。登录态补爬只适合你自己电脑，GitHub 云端用不了。

## 说明

- 投递前以企业官网为准
- 已过截止日期的岗位不会出现

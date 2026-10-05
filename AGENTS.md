# 项目约定

- `proxy.ini` 是 Subconverter 外部配置，不是可直接导入 Mihomo 的 YAML。
- 修改前读取 `memory.md`；节点匹配须按实际名称验证，不能仅检查分组引用。
- 不保存节点凭据，不将订阅或节点链接发送到第三方转换服务。
- 回归测试放在 `scripts/test/`，运行 `py -3 -B scripts/test/test_proxy_ini.py`；无 Python Launcher 时用 `python -B scripts/test/test_proxy_ini.py`。
- 离线分组校验、真实订阅转换与业务可用性是不同验证层，报告中必须区分。
- 任务完成后提取关键经验保存到 `memory.md`；不记录普通测试通过结果、临时数据或敏感信息。

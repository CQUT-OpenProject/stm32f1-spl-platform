# 上游兼容补丁

补丁是上游源码的修改，沿用对应源文件及 `vendor/st/` 中的许可证，不适用仓库自编写代码的 MIT 许可。

- `cmsis-compiler.patch`：将 GNU 分支中的四个裸函数改为只包含汇编，遵守 ARM 调用约定，允许 GCC 和 Clang 编译；为 STREX 输出增加 early-clobber 约束，避免输出寄存器与地址/数据重叠，并声明内存副作用。
- `system-clock.patch`：允许 HSI8 配置跳过默认 HSE/PLL 设置；初始化后根据真实寄存器更新 `SystemCoreClock`，包括 HSE 启动失败时的 HSI 回退。

`scripts/prepare_sources.py` 先检查所有上游文件的 SHA-256，再在构建目录创建 LF 换行的副本并应用补丁。原始文件（包括换行格式）不变。升级官方包时必须重新审查补丁，不允许静默跳过失败的补丁。

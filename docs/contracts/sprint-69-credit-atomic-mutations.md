# Sprint 69 合同：图片积分并发原子变更

## 目标

修复同一用户多个图片 job 并发生成时，积分占用和扣费基于旧账户余额写回，导致成功图片扣费阶段报 `图片生成积分占用不存在，无法扣费` 的问题。

## 范围内

- 图片生成积分占用、成功扣费和失败释放必须使用数据库原子 `UPDATE` 表达式更新 `balance` 与 `reserved_balance`。
- 余额不足、占用不存在时仍然明确失败，不能静默免费生成或吞掉扣费错误。
- 新增并发回归测试，覆盖同一用户多张图同时占用和同时扣费后的账户余额、占用余额和流水数量。
- 更新进度记录。

## 范围外

- 不改变积分面额、扣费价格、激活码、管理员调整积分规则。
- 不改变图片 job 队列、Provider 调用或任务重试语义。
- 不引入外部队列、分布式锁或兜底扣费逻辑。

## 交付物

- `backend/app/services/credits.py`
- `backend/tests/test_credits.py`
- `docs/progress.md`
- `docs/contracts/sprint-69-credit-atomic-mutations.md`

## 完成标准

- 同一用户并发图片 job 不会因为账户行旧值覆盖而丢失 `reserved_balance`。
- 没有可用积分或没有占用积分时继续返回原有明确错误。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_credits
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 当前修复仍保持小型项目的数据库事实来源和进程内 worker 架构，不升级为外部队列或分布式工作流。

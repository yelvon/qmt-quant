# Canvas 原型

本目录存放 **Cursor Canvas** 交互原型，用于 UI/交互设计评审。

| 文件 | 说明 |
|------|------|
| [qmt-quant-ui-mockup.canvas.tsx](./qmt-quant-ui-mockup.canvas.tsx) | qmt-quant 六页 UI 草稿（总览、数据、研究、验证、选股、实盘） |

## 在 Cursor 中预览

Canvas 需在 Cursor 管理的 `canvases` 目录下才能侧边交互预览。可选方式：

1. **直接打开本仓库文件**：在 Cursor 中打开 `canvases/qmt-quant-ui-mockup.canvas.tsx`，若支持则从编辑器预览。
2. **复制到工作区 Canvas 目录**（当前 workspace 为 `c:\github` 时）：

```powershell
Copy-Item "c:\github\qmt-quant\canvases\qmt-quant-ui-mockup.canvas.tsx" `
  "C:\Users\<你的用户名>\.cursor\projects\c-github\canvases\qmt-quant-ui-mockup.canvas.tsx" -Force
```

Git 以 **本目录** 为权威副本；Cursor 临时目录仅用于本地预览。

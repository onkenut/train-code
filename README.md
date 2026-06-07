# FlowForge - 本地可视化自动化工作流引擎

一个轻量级、纯本地运行的可视化自动化工作流引擎。通过 Web 界面拖拽节点连接成有向无环图（DAG），后端引擎负责解析 DAG 并调度执行，实现本地任务的自动化。

## ✨ 特性

### 🎨 可视化工作流编排
- 拖拽式节点操作，流畅的连线体验
- 支持条件分支节点（if/else 逻辑）
- 节点参数动态表单配置
- 画布缩放、平移、小地图预览

### ⚡ 核心执行引擎
- **DAG 解析与环路检测**：保存时自动校验循环依赖
- **拓扑排序**：自动确定执行层级
- **并行执行**：同一层级无依赖节点并发执行
- **事件驱动调度**：节点完成后自动触发下游节点，无需轮询
- **数据流转**：前置节点输出自动注入后置节点输入
- **上下文缓存**：LRU 缓存节点输出，避免重复计算

### 📊 运行时监控与控制
- WebSocket 实时日志推送（打字机效果）
- 节点级运行状态可视化
- 支持暂停/恢复/强制终止
- 执行历史记录查询

### 🔌 插件化节点系统
- 内核与业务逻辑分离
- 统一的 NodeModule 接口
- 新增节点仅需编写插件代码，无需修改引擎核心

## 🛠 技术栈

### 后端
- **Node.js** - 异步并发与流处理
- **Express** - Web 框架
- **better-sqlite3** - SQLite 数据库
- **ws** - WebSocket 实时通信
- **lru-cache** - 运行时上下文缓存
- **vm2** - 安全沙盒执行自定义脚本
- **axios** - HTTP 请求
- **node-cron** - 定时任务

### 前端
- **React 18** - UI 框架
- **Vite** - 构建工具
- **React Flow** - DAG 可视化画布
- **React Router** - 路由管理
- **Lucide React** - 图标库
- **Axios** - HTTP 客户端

## 📁 项目结构

```
FlowForge/
├── backend/                    # 后端服务
│   ├── src/
│   │   ├── index.js           # 服务入口
│   │   ├── db.js              # 数据库层
│   │   ├── websocket.js       # WebSocket 服务
│   │   ├── engine/            # 执行引擎
│   │   │   ├── dag.js         # DAG 解析与拓扑排序
│   │   │   └── WorkflowExecutor.js  # 核心执行器
│   │   ├── nodes/             # 节点插件系统
│   │   │   ├── base.js        # 节点基类
│   │   │   ├── registry.js    # 节点注册表
│   │   │   ├── HttpRequestNode.js
│   │   │   ├── ConditionNode.js
│   │   │   ├── DataTransformNode.js
│   │   │   ├── CronTriggerNode.js
│   │   │   ├── JsonExtractorNode.js
│   │   │   └── SendEmailNode.js
│   │   └── routes/            # API 路由
│   │       ├── workflows.js
│   │       └── executions.js
│   ├── data/                  # 数据库文件目录
│   └── package.json
│
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── main.jsx           # 入口文件
│   │   ├── App.jsx            # 根组件
│   │   ├── api/               # API 封装
│   │   ├── components/        # 通用组件
│   │   │   ├── CustomNode.jsx
│   │   │   ├── NodeSidebar.jsx
│   │   │   └── PropertiesPanel.jsx
│   │   ├── pages/             # 页面组件
│   │   │   ├── WorkflowList.jsx
│   │   │   ├── WorkflowEditor.jsx
│   │   │   └── ExecutionDetail.jsx
│   │   └── styles/
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
└── package.json               # 根配置（monorepo）
```

## 🚀 快速开始

### 环境要求
- Node.js >= 18
- npm >= 9

### 安装依赖

```bash
# 安装根目录依赖
npm install

# 安装前后端依赖
npm run install:all
```

### 开发模式

```bash
# 同时启动前后端
npm run dev

# 或分别启动
npm run dev:backend   # 后端: http://localhost:3001
npm run dev:frontend  # 前端: http://localhost:3000
```

### 生产构建

```bash
# 构建前端
npm run build

# 启动后端（同时托管前端静态文件）
npm run start
```

## 📦 内置节点类型

| 类型 | 名称 | 描述 |
|------|------|------|
| `cronTrigger` | 定时触发器 | 按 Cron 表达式定时触发 |
| `httpRequest` | HTTP 请求 | 发送 HTTP 请求获取数据 |
| `condition` | 条件分支 | 根据条件判断走不同分支 |
| `dataTransform` | 数据处理 | 转换和处理数据（支持脚本） |
| `jsonExtractor` | JSON 提取 | 从 JSON 数据中提取字段 |
| `sendEmail` | 发送邮件 | 发送邮件通知 |

## 🔧 如何新增节点

1. 在 `backend/src/nodes/` 下创建新的节点类，继承 `BaseNode`
2. 实现 `execute(input, context)` 方法
3. 在 `registry.js` 中注册节点类型

**示例：新增一个节点只需约 30 行代码**

```javascript
// backend/src/nodes/MyCustomNode.js
const BaseNode = require('./base');

class MyCustomNode extends BaseNode {
  async execute(input, context) {
    const { param1, param2 } = this.config;
    return {
      success: true,
      result: param1 + param2,
      input
    };
  }
}

module.exports = MyCustomNode;
```

在 `registry.js` 中注册：

```javascript
registerNode('myCustom', MyCustomNode, {
  label: '我的自定义节点',
  category: 'data',
  icon: 'star',
  description: '自定义节点描述',
  defaultConfig: {
    param1: '默认值1',
    param2: '默认值2'
  },
  inputs: 1,
  outputs: 1
});
```

## 🏗 架构亮点

### DAG 环路检测
使用深度优先搜索（DFS）算法，在保存工作流时自动检测是否存在循环依赖，防止死循环。

### 基于事件的调度器
节点执行完毕后通过事件通知机制，检查下游节点的所有前置依赖是否已满足，若满足则立刻推入执行队列。不使用轮询，效率更高。

### 上下文缓存优化
使用 LRU 缓存存储节点输出结果，以 `execution_id + node_id` 为 Key，避免重复落盘读库。执行结束后自动清理。

### 安全沙盒执行
数据处理节点的自定义脚本使用 `vm2` 在受限沙盒中执行，限制文件系统和网络访问，防止恶意代码执行。

## 📊 数据模型

### workflows - 工作流定义
| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | UUID |
| name | TEXT | 工作流名称 |
| dsl_json | TEXT | 画布结构定义（JSON） |
| status | TEXT | 运行状态 |
| created_at | TIMESTAMP | 创建时间 |

### executions - 执行历史记录
| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 执行记录 UUID |
| workflow_id | TEXT FK | 关联工作流 |
| trigger_type | TEXT | 触发方式（手动/Cron） |
| status | TEXT | 整体执行状态 |
| started_at | TIMESTAMP | 开始时间 |
| finished_at | TIMESTAMP | 结束时间 |

### execution_logs - 节点级执行日志
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| execution_id | TEXT FK | 关联执行记录 |
| node_id | TEXT | 节点在 DSL 中的唯一标识 |
| status | TEXT | 该节点执行状态 |
| input_data | TEXT | 节点接收的输入 |
| output_data | TEXT | 节点的输出 |
| error_msg | TEXT | 错误信息 |
| started_at | TIMESTAMP | 开始时间 |
| finished_at | TIMESTAMP | 结束时间 |

## 🔗 API 接口

### 工作流管理
- `GET /api/workflows` - 获取工作流列表
- `GET /api/workflows/node-types` - 获取节点类型定义
- `GET /api/workflows/:id` - 获取工作流详情
- `POST /api/workflows` - 创建工作流
- `PUT /api/workflows/:id` - 更新工作流
- `DELETE /api/workflows/:id` - 删除工作流
- `POST /api/workflows/:id/execute` - 执行工作流
- `GET /api/workflows/:id/executions` - 获取工作流执行历史

### 执行控制
- `GET /api/executions` - 获取执行列表
- `GET /api/executions/:id` - 获取执行详情
- `GET /api/executions/:id/logs` - 获取执行日志
- `POST /api/executions/:id/pause` - 暂停执行
- `POST /api/executions/:id/resume` - 恢复执行
- `POST /api/executions/:id/terminate` - 终止执行

## 📝 License

MIT

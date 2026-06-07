import React from 'react';
import { Clock, Globe, SplitSquareHorizontal, Database, Mail, Code, FileJson } from 'lucide-react';

const iconMap = {
  clock: Clock,
  globe: Globe,
  split: SplitSquareHorizontal,
  transform: Database,
  json: FileJson,
  mail: Mail,
  code: Code
};

const categoryLabels = {
  trigger: '触发器',
  network: '网络',
  logic: '逻辑',
  data: '数据',
  notification: '通知'
};

function NodeSidebar({ nodeTypes }) {
  const categories = {};
  nodeTypes.forEach(type => {
    if (!categories[type.category]) {
      categories[type.category] = [];
    }
    categories[type.category].push(type);
  });

  const onDragStart = (event, nodeType) => {
    console.log('Dragging node type:', nodeType.type);
    event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeType));
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div style={{
      width: '256px',
      backgroundColor: '#1e293b',
      borderRight: '1px solid #334155',
      height: '100%',
      overflowY: 'auto',
      flexShrink: 0
    }}>
      <div style={{
        padding: '16px',
        borderBottom: '1px solid #334155'
      }}>
        <h2 style={{
          fontSize: '18px',
          fontWeight: 600,
          color: '#ffffff',
          margin: 0
        }}>节点库</h2>
        <p style={{
          fontSize: '12px',
          color: '#94a3b8',
          marginTop: '4px',
          margin: 0
        }}>拖拽节点到画布</p>
      </div>

      <div style={{ padding: '12px' }}>
        {Object.entries(categories).map(([category, types]) => (
          <div key={category} style={{ marginBottom: '16px' }}>
            <h3 style={{
              fontSize: '11px',
              fontWeight: 600,
              color: '#64748b',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '8px',
              padding: '0 4px'
            }}>
              {categoryLabels[category] || category}
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {types.map(nodeType => {
                const IconComponent = iconMap[nodeType.icon] || Code;
                return (
                  <div
                    key={nodeType.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, nodeType)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px',
                      backgroundColor: 'rgba(51, 65, 85, 0.5)',
                      borderRadius: '6px',
                      cursor: 'grab',
                      transition: 'background-color 0.15s'
                    }}
                    onMouseOver={(e) => { e.currentTarget.style.backgroundColor = '#334155'; }}
                    onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'rgba(51, 65, 85, 0.5)'; }}
                  >
                    <IconComponent size={16} style={{ color: '#818cf8', flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: '14px',
                        color: '#ffffff',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis'
                      }}>{nodeType.label}</div>
                      <div style={{
                        fontSize: '12px',
                        color: '#94a3b8',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis'
                      }}>{nodeType.description}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default NodeSidebar;

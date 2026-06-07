import React from 'react';
import { Handle, Position } from 'reactflow';
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

const categoryColors = {
  trigger: { bg: '#065f46', border: '#059669' },
  network: { bg: '#1e3a8a', border: '#2563eb' },
  logic: { bg: '#78350f', border: '#d97706' },
  data: { bg: '#581c87', border: '#9333ea' },
  notification: { bg: '#991b1b', border: '#dc2626' }
};

function CustomNode({ data, isConnectable, selected }) {
  const IconComponent = iconMap[data.icon] || Code;
  const colors = categoryColors[data.category] || { bg: '#1e293b', border: '#475569' };

  const borderColor = selected ? '#6366f1' : colors.border;

  const handleStyle = {
    width: '10px',
    height: '10px',
    backgroundColor: '#6366f1',
    border: '2px solid #fff',
    borderRadius: '50%',
    zIndex: 10
  };

  return (
    <div
      style={{
        minWidth: '160px',
        borderRadius: '8px',
        overflow: 'hidden',
        backgroundColor: '#1e293b',
        border: `2px solid ${borderColor}`,
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)'
      }}
    >
      {data.inputs > 0 && (
        <Handle
          type="target"
          position={Position.Left}
          isConnectable={isConnectable}
          style={handleStyle}
        />
      )}

      <div
        style={{
          padding: '8px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          backgroundColor: colors.bg
        }}
      >
        <IconComponent size={16} style={{ color: '#fff', flexShrink: 0 }} />
        <span style={{
          color: '#fff',
          fontSize: '14px',
          fontWeight: 500,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis'
        }}>
          {data.label}
        </span>
      </div>

      <div style={{
        padding: '8px 12px',
        fontSize: '12px',
        color: '#94a3b8'
      }}>
        {data.description || data.type}
      </div>

      {data.outputLabels && data.outputLabels.length > 1 ? (
        <>
          <Handle
            type="source"
            position={Position.Right}
            id="true"
            isConnectable={isConnectable}
            style={{ ...handleStyle, backgroundColor: '#22c55e', top: '30%' }}
          />
          <Handle
            type="source"
            position={Position.Right}
            id="false"
            isConnectable={isConnectable}
            style={{ ...handleStyle, backgroundColor: '#ef4444', top: '70%' }}
          />
        </>
      ) : (
        <Handle
          type="source"
          position={Position.Right}
          isConnectable={isConnectable}
          style={handleStyle}
        />
      )}
    </div>
  );
}

export default CustomNode;

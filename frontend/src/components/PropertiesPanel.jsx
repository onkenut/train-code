import React from 'react';
import { X, Save } from 'lucide-react';

function PropertiesPanel({ selectedNode, onUpdateNode, onClose }) {
  if (!selectedNode) {
    return (
      <div style={{
        width: '320px',
        backgroundColor: '#1e293b',
        borderLeft: '1px solid #334155',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0
      }}>
        <div style={{
          padding: '16px',
          borderBottom: '1px solid #334155',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#ffffff', margin: 0 }}>属性面板</h2>
        </div>
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#64748b',
          fontSize: '14px'
        }}>
          选择一个节点以编辑属性
        </div>
      </div>
    );
  }

  const handleConfigChange = (key, value) => {
    onUpdateNode(selectedNode.id, {
      ...selectedNode.data,
      data: {
        ...selectedNode.data.data,
        [key]: value
      }
    });
  };

  const renderConfigField = (key, value) => {
    if (typeof value === 'object' && value !== null) {
      return (
        <div key={key} style={{ marginBottom: '16px' }}>
          <label style={{
            display: 'block',
            fontSize: '14px',
            fontWeight: 500,
            color: '#cbd5e1',
            marginBottom: '8px'
          }}>{key}</label>
          <textarea
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: '#334155',
              border: '1px solid #475569',
              borderRadius: '6px',
              color: '#ffffff',
              fontSize: '14px',
              outline: 'none',
              resize: 'vertical',
              minHeight: '80px',
              fontFamily: 'monospace'
            }}
            rows={3}
            value={JSON.stringify(value, null, 2)}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                handleConfigChange(key, parsed);
              } catch (err) {}
            }}
          />
        </div>
      );
    }

    if (typeof value === 'boolean') {
      return (
        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <input
            type="checkbox"
            checked={value}
            onChange={(e) => handleConfigChange(key, e.target.checked)}
            style={{
              width: '16px',
              height: '16px',
              borderRadius: '4px',
              border: '1px solid #475569',
              backgroundColor: '#334155'
            }}
          />
          <label style={{ fontSize: '14px', fontWeight: 500, color: '#cbd5e1' }}>{key}</label>
        </div>
      );
    }

    if (key === 'method') {
      return (
        <div key={key} style={{ marginBottom: '16px' }}>
          <label style={{
            display: 'block',
            fontSize: '14px',
            fontWeight: 500,
            color: '#cbd5e1',
            marginBottom: '8px'
          }}>请求方法</label>
          <select
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: '#334155',
              border: '1px solid #475569',
              borderRadius: '6px',
              color: '#ffffff',
              fontSize: '14px',
              outline: 'none'
            }}
            value={value}
            onChange={(e) => handleConfigChange(key, e.target.value)}
          >
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="DELETE">DELETE</option>
            <option value="PATCH">PATCH</option>
          </select>
        </div>
      );
    }

    if (key === 'operator') {
      return (
        <div key={key} style={{ marginBottom: '16px' }}>
          <label style={{
            display: 'block',
            fontSize: '14px',
            fontWeight: 500,
            color: '#cbd5e1',
            marginBottom: '8px'
          }}>操作符</label>
          <select
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: '#334155',
              border: '1px solid #475569',
              borderRadius: '6px',
              color: '#ffffff',
              fontSize: '14px',
              outline: 'none'
            }}
            value={value}
            onChange={(e) => handleConfigChange(key, e.target.value)}
          >
            <option value="===">=== (严格等于)</option>
            <option value="!==">!== (严格不等于)</option>
            <option value="==">== (等于)</option>
            <option value="!=">!= (不等于)</option>
            <option value=">">大于</option>
            <option value=">=">大于等于</option>
            <option value="<">小于</option>
            <option value="<=">小于等于</option>
            <option value="contains">包含</option>
            <option value="startsWith">开头</option>
            <option value="endsWith">结尾</option>
          </select>
        </div>
      );
    }

    const isTextarea = typeof value === 'string' && value.length > 50;

    return (
      <div key={key} style={{ marginBottom: '16px' }}>
        <label style={{
          display: 'block',
          fontSize: '14px',
          fontWeight: 500,
          color: '#cbd5e1',
          marginBottom: '8px'
        }}>{key}</label>
        {isTextarea ? (
          <textarea
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: '#334155',
              border: '1px solid #475569',
              borderRadius: '6px',
              color: '#ffffff',
              fontSize: '14px',
              outline: 'none',
              resize: 'vertical',
              minHeight: '80px',
              fontFamily: 'monospace'
            }}
            rows={4}
            value={value}
            onChange={(e) => handleConfigChange(key, e.target.value)}
          />
        ) : (
          <input
            type="text"
            style={{
              width: '100%',
              padding: '8px 12px',
              backgroundColor: '#334155',
              border: '1px solid #475569',
              borderRadius: '6px',
              color: '#ffffff',
              fontSize: '14px',
              outline: 'none'
            }}
            value={value}
            onChange={(e) => handleConfigChange(key, e.target.value)}
          />
        )}
      </div>
    );
  };

  const config = selectedNode.data.data || {};

  return (
    <div style={{
      width: '320px',
      backgroundColor: '#1e293b',
      borderLeft: '1px solid #334155',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0
    }}>
      <div style={{
        padding: '16px',
        borderBottom: '1px solid #334155',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#ffffff', margin: 0 }}>属性面板</h2>
        <button
          onClick={onClose}
          style={{
            padding: '4px',
            backgroundColor: 'transparent',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            color: '#94a3b8'
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.backgroundColor = '#334155';
            e.currentTarget.style.color = '#ffffff';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.color = '#94a3b8';
          }}
        >
          <X size={18} />
        </button>
      </div>

      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px'
      }}>
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            fontSize: '14px',
            fontWeight: 600,
            color: '#818cf8',
            marginBottom: '12px'
          }}>
            {selectedNode.data.label}
          </h3>
          <p style={{
            fontSize: '12px',
            color: '#64748b',
            marginBottom: '16px'
          }}>
            节点 ID: {selectedNode.id}
          </p>
        </div>

        <div>
          {Object.entries(config).map(([key, value]) => renderConfigField(key, value))}
        </div>
      </div>

      <div style={{
        padding: '16px',
        borderTop: '1px solid #334155'
      }}>
        <p style={{
          fontSize: '12px',
          color: '#64748b',
          margin: 0
        }}>
          提示: 使用 ${'${变量名}'} 引用前置节点的输出
        </p>
      </div>
    </div>
  );
}

export default PropertiesPanel;

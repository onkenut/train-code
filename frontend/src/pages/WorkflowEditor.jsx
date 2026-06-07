import React, { useState, useCallback, useRef, useEffect } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  MiniMap,
  Background,
  MarkerType
} from 'reactflow';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Play, Save, Trash2, AlertCircle } from 'lucide-react';
import CustomNode from '../components/CustomNode';
import NodeSidebar from '../components/NodeSidebar';
import PropertiesPanel from '../components/PropertiesPanel';
import { workflows } from '../api';

const nodeTypes = {
  custom: CustomNode
};

function WorkflowEditorContent() {
  const { id } = useParams();
  const navigate = useNavigate();
  const reactFlowWrapper = useRef(null);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [nodeTypesList, setNodeTypesList] = useState([]);
  const [workflowName, setWorkflowName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    workflows.getNodeTypes().then(res => setNodeTypesList(res.data));
  }, []);

  useEffect(() => {
    if (id && id !== 'new') {
      workflows.get(id).then(res => {
        setWorkflowName(res.data.name);
        if (res.data.dsl_json) {
          try {
            const dsl = JSON.parse(res.data.dsl_json);
            setNodes(dsl.nodes.map(n => {
              let nodeData;
              if (n.data && n.data.config !== undefined) {
                nodeData = {
                  type: n.type,
                  label: n.data.label,
                  icon: n.data.icon,
                  category: n.data.category,
                  description: n.data.description,
                  inputs: n.data.inputs,
                  outputs: n.data.outputs,
                  outputLabels: n.data.outputLabels,
                  data: n.data.config
                };
              } else {
                const nodeType = nodeTypesList.find(t => t.type === n.type) || {};
                nodeData = {
                  type: n.type,
                  label: nodeType.label || n.type,
                  icon: nodeType.icon || 'code',
                  category: nodeType.category || 'data',
                  description: nodeType.description || '',
                  inputs: nodeType.inputs,
                  outputs: nodeType.outputs,
                  outputLabels: nodeType.outputLabels,
                  data: n.data
                };
              }
              return {
                id: n.id,
                type: 'custom',
                position: n.position,
                data: nodeData
              };
            }));
            setEdges(dsl.edges.map(e => ({
              ...e,
              markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1' },
              style: { stroke: '#6366f1', strokeWidth: 2 }
            })));
          } catch (e) {
            console.error('Failed to parse DSL:', e);
          }
        }
      });
    } else {
      setWorkflowName('新建工作流');
    }
  }, [id, setNodes, setEdges, nodeTypesList]);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(
      {
        ...params,
        markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1' },
        style: { stroke: '#6366f1', strokeWidth: 2 }
      },
      eds
    )),
    [setEdges]
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();

      if (!reactFlowWrapper.current || !reactFlowInstance) {
        console.warn('ReactFlow instance not ready');
        return;
      }

      const nodeTypeData = event.dataTransfer.getData('application/reactflow');

      if (!nodeTypeData) {
        console.warn('No node type data found in drop event');
        return;
      }

      try {
        const nodeType = JSON.parse(nodeTypeData);
        const bounds = reactFlowWrapper.current.getBoundingClientRect();
        const position = reactFlowInstance.project({
          x: event.clientX - bounds.left,
          y: event.clientY - bounds.top,
        });

        const newNode = {
          id: `${nodeType.type}_${Date.now()}`,
          type: 'custom',
          position,
          data: {
            ...nodeType,
            data: { ...nodeType.defaultConfig }
          }
        };

        setNodes((nds) => nds.concat(newNode));
      } catch (e) {
        console.error('Failed to parse node type data:', e);
      }
    },
    [reactFlowInstance, setNodes]
  );

  const handleNodeClick = useCallback((event, node) => {
    setSelectedNode(node);
  }, []);

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const handleUpdateNode = useCallback((nodeId, newData) => {
    setNodes((nds) =>
      nds.map((node) =>
        node.id === nodeId
          ? { ...node, data: newData }
          : node
      )
    );
    setSelectedNode(prev => prev?.id === nodeId ? { ...prev, data: newData } : prev);
  }, [setNodes]);

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);

    const dsl = {
      nodes: nodes.map(n => ({
        id: n.id,
        type: n.data.type,
        position: n.position,
        data: {
          label: n.data.label,
          icon: n.data.icon,
          category: n.data.category,
          description: n.data.description,
          inputs: n.data.inputs,
          outputs: n.data.outputs,
          outputLabels: n.data.outputLabels,
          config: n.data.data
        }
      })),
      edges: edges.map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle
      }))
    };

    try {
      if (id && id !== 'new') {
        await workflows.update(id, { name: workflowName, dsl_json: dsl });
      } else {
        const res = await workflows.create({ name: workflowName, dsl_json: dsl });
        navigate(`/workflow/${res.data.id}`, { replace: true });
      }
    } catch (err) {
      setError(err.response?.data?.error || '保存失败');
    } finally {
      setIsSaving(false);
    }
  };

  const handleExecute = async () => {
    if (id && id !== 'new') {
      try {
        const res = await workflows.execute(id);
        navigate(`/execution/${res.data.executionId}`);
      } catch (err) {
        setError(err.response?.data?.error || '执行失败');
      }
    }
  };

  const handleDeleteNode = () => {
    if (selectedNode) {
      setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
      setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
      setSelectedNode(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', backgroundColor: '#0f172a' }}>
      <div style={{ 
        height: '56px', 
        backgroundColor: '#1e293b', 
        borderBottom: '1px solid #334155', 
        display: 'flex', 
        alignItems: 'center', 
        padding: '0 16px', 
        gap: '16px',
        flexShrink: 0
      }}>
        <button
          onClick={() => navigate('/')}
          style={{
            padding: '8px',
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
          <ArrowLeft size={20} />
        </button>

        <input
          type="text"
          value={workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
          style={{
            backgroundColor: 'transparent',
            color: '#ffffff',
            fontSize: '18px',
            fontWeight: 500,
            outline: 'none',
            border: 'none',
            borderBottom: '2px solid transparent',
            padding: '4px'
          }}
          onFocus={(e) => { e.currentTarget.style.borderBottomColor = '#6366f1'; }}
          onBlur={(e) => { e.currentTarget.style.borderBottomColor = 'transparent'; }}
          placeholder="工作流名称"
        />

        <div style={{ flex: 1 }} />

        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f87171', fontSize: '14px' }}>
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        <button
          onClick={handleDeleteNode}
          disabled={!selectedNode}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            backgroundColor: selectedNode ? 'rgba(220, 38, 38, 0.2)' : 'rgba(220, 38, 38, 0.1)',
            color: selectedNode ? '#f87171' : '#6b7280',
            borderRadius: '6px',
            border: 'none',
            cursor: selectedNode ? 'pointer' : 'not-allowed',
            fontSize: '14px'
          }}
        >
          <Trash2 size={16} />
          删除节点
        </button>

        <button
          onClick={handleSave}
          disabled={isSaving}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 16px',
            backgroundColor: '#4f46e5',
            color: '#ffffff',
            borderRadius: '6px',
            border: 'none',
            cursor: isSaving ? 'not-allowed' : 'pointer',
            opacity: isSaving ? 0.5 : 1,
            fontSize: '14px'
          }}
        >
          <Save size={16} />
          {isSaving ? '保存中...' : '保存'}
        </button>

        <button
          onClick={handleExecute}
          disabled={!id || id === 'new'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 16px',
            backgroundColor: (!id || id === 'new') ? '#1e3a2f' : '#16a34a',
            color: (!id || id === 'new') ? '#6b7280' : '#ffffff',
            borderRadius: '6px',
            border: 'none',
            cursor: (!id || id === 'new') ? 'not-allowed' : 'pointer',
            fontSize: '14px'
          }}
        >
          <Play size={16} />
          执行
        </button>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <NodeSidebar nodeTypes={nodeTypesList} />

        <div 
          ref={reactFlowWrapper}
          style={{ flex: 1, height: '100%', position: 'relative' }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={setReactFlowInstance}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onNodeClick={handleNodeClick}
            onPaneClick={handlePaneClick}
            nodeTypes={nodeTypes}
            fitView
            style={{ height: '100%', width: '100%', backgroundColor: '#0f172a' }}
            deleteKeyCode={['Delete', 'Backspace']}
          >
            <Controls style={{ backgroundColor: '#1e293b', border: '1px solid #334155' }} />
            <MiniMap
              nodeStrokeColor={(n) => {
                if (n.data?.category === 'trigger') return '#059669';
                if (n.data?.category === 'network') return '#2563eb';
                if (n.data?.category === 'logic') return '#d97706';
                if (n.data?.category === 'data') return '#9333ea';
                if (n.data?.category === 'notification') return '#dc2626';
                return '#475569';
              }}
              nodeColor={() => '#1e293b'}
              style={{ backgroundColor: '#1e293b' }}
            />
            <Background color="#334155" gap={16} />
          </ReactFlow>
        </div>

        <PropertiesPanel
          selectedNode={selectedNode}
          onUpdateNode={handleUpdateNode}
          onClose={() => setSelectedNode(null)}
        />
      </div>
    </div>
  );
}

function WorkflowEditor() {
  return (
    <ReactFlowProvider>
      <WorkflowEditorContent />
    </ReactFlowProvider>
  );
}

export default WorkflowEditor;

function parseDSL(dslJson) {
  const dsl = typeof dslJson === 'string' ? JSON.parse(dslJson) : dslJson;
  const nodes = new Map();
  const edges = [];

  if (dsl.nodes) {
    dsl.nodes.forEach(node => {
      let nodeData = node.data || {};
      if (nodeData.config !== undefined) {
        nodeData = nodeData.config;
      }
      nodes.set(node.id, {
        id: node.id,
        type: node.type,
        data: nodeData,
        position: node.position
      });
    });
  }

  if (dsl.edges) {
    dsl.edges.forEach(edge => {
      edges.push({
        source: edge.source,
        target: edge.target,
        id: edge.id,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle
      });
    });
  }

  return { nodes, edges };
}

function detectCycle(nodes, edges) {
  const adj = new Map();
  const visited = new Set();
  const recStack = new Set();

  nodes.forEach((_, nodeId) => adj.set(nodeId, []));
  edges.forEach(edge => {
    if (adj.has(edge.source)) {
      adj.get(edge.source).push(edge.target);
    }
  });

  function dfs(nodeId) {
    visited.add(nodeId);
    recStack.add(nodeId);

    const neighbors = adj.get(nodeId) || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        if (dfs(neighbor)) return true;
      } else if (recStack.has(neighbor)) {
        return true;
      }
    }

    recStack.delete(nodeId);
    return false;
  }

  for (const [nodeId] of nodes) {
    if (!visited.has(nodeId)) {
      if (dfs(nodeId)) return true;
    }
  }

  return false;
}

function topologicalSort(nodes, edges) {
  const inDegree = new Map();
  const adj = new Map();

  nodes.forEach((_, nodeId) => {
    inDegree.set(nodeId, 0);
    adj.set(nodeId, []);
  });

  edges.forEach(edge => {
    if (adj.has(edge.source) && adj.has(edge.target)) {
      adj.get(edge.source).push(edge.target);
      inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
    }
  });

  const queue = [];
  const levels = [];
  let currentLevel = [];

  inDegree.forEach((degree, nodeId) => {
    if (degree === 0) {
      currentLevel.push(nodeId);
    }
  });

  while (currentLevel.length > 0) {
    levels.push([...currentLevel]);
    const nextLevel = [];

    currentLevel.forEach(nodeId => {
      const neighbors = adj.get(nodeId) || [];
      neighbors.forEach(neighbor => {
        const newDegree = inDegree.get(neighbor) - 1;
        inDegree.set(neighbor, newDegree);
        if (newDegree === 0) {
          nextLevel.push(neighbor);
        }
      });
    });

    currentLevel = nextLevel;
  }

  const visitedCount = levels.reduce((sum, level) => sum + level.length, 0);
  if (visitedCount !== nodes.size) {
    throw new Error('DAG contains a cycle or unreachable nodes');
  }

  return levels;
}

function getPredecessors(nodeId, edges) {
  return edges
    .filter(edge => edge.target === nodeId)
    .map(edge => edge.source);
}

function getSuccessors(nodeId, edges) {
  return edges
    .filter(edge => edge.source === nodeId)
    .map(edge => edge.target);
}

module.exports = {
  parseDSL,
  detectCycle,
  topologicalSort,
  getPredecessors,
  getSuccessors
};

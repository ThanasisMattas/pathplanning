# utils.py is part of PathPlanning
#
# PathPlanning is free software; you may redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. You should have received a copy of the GNU
# General Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
#
# (C) 2020 Athanasios Mattas
# =======================================================================
"""Houses some utility functions."""

import ast
from datetime import datetime, timedelta
from itertools import combinations
from functools import wraps
from operator import itemgetter
import random
from timeit import default_timer as timer
from typing import Iterable

import click
import matplotlib.pyplot as plt
import networkx as nx


def plot_graph(G, paths_data, disconnected_nodes):
  """Plots the graph and all the generated paths in spring_layout."""
  # pos = nx.spring_layout(G)
  pos = nx.spring_layout(G)

  # Layouts
  # -------
  # circular_layout
  # spring_layout                <--
  # fruchterman_reingold_layout  <--
  # spiral_layout                <--

  # 1. Draw the graph
  nx.draw_networkx(G, pos, node_size=450, width=0.2, alpha=0.3,
                   with_labels=False)
  # 2. Draw the disconnected nodes
  nx.draw_networkx_nodes(G, pos=pos, nodelist=disconnected_nodes, node_color='r',
                         node_shape='x', node_size=800, linewidths=3)

  # colors = iter(['b', 'm', 'g', 'k', 'r', 'c', 'y', 'w'])
  colors = iter(['mediumblue', 'm', 'g', 'k', 'r', 'c', 'y', 'w'])
  # Accumulates all the nodes of all the paths for label drawing.
  paths_nodes = set()

  for path in paths_data:
    paths_nodes.update(path[0])

  # Change the font of the labels of the path nodes and restore alpha=None.
  for node, (x, y) in pos.items():
    if node in paths_nodes:
      plt.text(x, y, node, fontsize=14, ha='center', va='center')

  # 3. Draw the nodes of all the paths
  nx.draw_networkx_nodes(G, pos=pos, nodelist=paths_nodes, node_size=700,
                         edgecolors='k', node_color="deepskyblue")

  # 4. Draw the paths
  for i, path in enumerate(paths_data):
    color = next(colors)
    path_edges_sequence = list(zip(path[0], path[0][1:]))

    label = (f"path_{i + 1}: {str(path[0])}\ncost: {path[1]}    "
             f"disconnected nodes: {str(path[2])}")

    # Draw the path
    nx.draw_networkx_edges(G, pos=pos, edgelist=path_edges_sequence,
                           edge_color=color,
                           width=len(paths_data) + 14 - 4 * i, label=label)

    # Mark the disconnceted node with an X.
    nx.draw_networkx_nodes(G, pos=pos, nodelist=path[2], node_color=color,
                           node_shape='x', node_size=800, linewidths=3)

  # Draw 'Start' & 'End' labels.
  # labels = {paths_data[0][0][0]: "Start", paths_data[0][0][-1]: "End"}
  # for node, (x, y) in pos.items():
  #   if node in labels.keys():
  #     plt.text(x + 50, y + 50, node, fontsize=14, ha='center', va='center')
  # nx.draw_networkx_labels(G, pos=pos, labels=labels,
  #                         font_color='k', font_size=20,
  #                         bbox=dict(boxstyle="square", fc='w', ec='k'))

  plt.title(f"#nodes: {G.number_of_nodes()}    #edges: {G.number_of_edges()}")
  plt.legend()
  plt.show()


def _edge_weight_bias(edge, num_nodes) -> float:
  """Penalizes edges that connect distant nodes.

  Args:
    edge (tuple)    : (tail, head)
    num_nodes (int) : used for normalization to 1

  Returns:
    bias (float)    : takes values in [0, 1]
  """
  # Bias will be capped with one of [0.1, 0.2, ..., 1.0], depending on with bin
  # it falls into.
  bias_bins = [0.1 * i**2 for i in range(1, 11)]
  bias = abs(edge[0] - edge[1]) / num_nodes
  for b in bias_bins:
    if bias < b:
      bias = b
      break
  return bias


def random_graph(num_nodes,
                 weighted=True,
                 weights_on="edges",
                 max_edge_weight=1000,
                 max_node_weight=1000,
                 random_seed=None):
  """Generates a random graph of <num_nodes>, using the Erdős–Rényi model.

  The graph is represented by its adjacency list. NetworkX is used only for
  plotting.

  Args:
    num_nodes (int)       : number of nodes
    weighted (bool)       : defaults to True
    weights_on (string)   : 'edges', 'nodes' or 'edges-and-nodes'
    max_edge_weight (int) : each edge has a random weight from 0 to
                            max_edge_weight (defaults to 100)
    max_node_weight (int) : each node has a random weight from 0 to
                            max_node_weight (defaults to 100)
    random_seed (int)     : in case of fixed random graph (defaults to None)

  Returns:
    adj_list (list)       : the adjacency list
                            each element is a list of tuples (neighbor, weight)
                            of the neighbors of each node
    G (Graph)             : used to plot the graph
  """
  if random_seed is None:
    random_seed = datetime.now
    # random_seed = 99
  random.seed(random_seed)

  nodes = list(range(1, num_nodes + 1))
  edges = set()
  adj_list = [set() for _ in range(num_nodes + 1)]
  G = nx.Graph()
  G.add_nodes_from(nodes)
  if weights_on in ["nodes", "edges-and-nodes"]:
    node_weights = random.choices(range(max_node_weight + 1), k=num_nodes + 1)

  # When nodes have weights, the weight that each neighbor holds at the
  # adjacency list (the edge weight) is increased by by its node-weight.
  # Whereas this holds true in the case of the adjacency list, it is not
  # correct when adding the weighted edges to the Graph object, but that's ok,
  # because the Graph object is used only for plotting.
  weight_mode = "not-weighted" if not weighted else weights_on

  weight = {
    "not-weighted": lambda _, __: 1,
    "edges": lambda _, bias: round(bias * random.randint(0, max_edge_weight)),
    "nodes": lambda node_id, _: node_weights[node_id],
    "edges-and-nodes": lambda node_id, bias: (
      node_weights[node_id] + round(bias * random.randint(0, max_edge_weight))
    )
  }

  # Iterate through all possible edges and randomly deside which to keep.
  for edge in combinations(nodes, 2):
    # The closer the nodes are, the more probable it is that they are connected
    # with an edge and the edge-weight is lower. (This way, it is more
    # realistic - edges of nearby nodes cost less - and paths with too few
    # nodes, that go straight to the end, are avoided.)
    # Namely, distance (up) (down) edge_probability.
    edge_probability = max(0, 1 - abs(edge[0] - edge[1]) / num_nodes - 0.5)
    random_probability = random.random()
    if edge_probability > random_probability:
      bias = _edge_weight_bias(edge, num_nodes)
      edges.add((*edge, weight[weight_mode](edge[1], bias)))
      adj_list[edge[0]].add((edge[1], weight[weight_mode](edge[1], bias)))
      adj_list[edge[1]].add((edge[0], weight[weight_mode](edge[0], bias)))

  G.add_weighted_edges_from(edges)
  return adj_list, G


def print_duration(start, end, process):
    """Prints the duration of a process."""
    process_name = {
        "main": "Total",
    }
    if process in process_name:
        process = process_name[process]
    prefix = f"{process.capitalize()} duration"
    duration = timedelta(seconds=end - start)
    print(f"{prefix:-<30}{duration}"[:40])


def time_this(f):
    """function timer decorator

    - Uses wraps to preserve the metadata of the decorated function
      (__name__ and __doc__)
    - logs the duration
    - prints the duration

    Args:
        f(funtion)      : the function to be decorated

    Returns:
        wrap (callable) : returns the result of the decorated function
    """
    assert callable(f)

    @wraps(f)
    def wrap(*args, **kwargs):
        start = timer()
        result = f(*args, **kwargs)
        end = timer()
        print_duration(start, end, f.__name__)
        return result
    return wrap


class PythonLiteralOption(click.Option):

    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except:
            raise click.BadParameter(value)


def check_nodal_connection(nodes: Iterable,
                           adj_list: list,
                           disconnected_nodes: Iterable) -> Iterable:
  """Checks for connection status of important nodes, i.e. start node and,
  in case of a disconnected important node, it replaces it with the closest
  neighbor.
  """
  for i, node in enumerate(nodes):
    if node in disconnected_nodes:
      input(f"Node <{node}> is disconnected. Setting it to its closest "
            "first neighbor. Press ENTER to continue...")
      node_neighbors = sorted(adj_list[node], key=itemgetter(1))
      for neighbor in node_neighbors:
        if neighbor[1] not in disconnected_nodes:
          nodes[i] = neighbor[1]
          break
  return nodes

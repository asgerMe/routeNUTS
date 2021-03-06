from module.RouteGame import routeGame as game
import numpy as np
import matplotlib.pyplot as plt
import itertools

class Sample:

    def __init__(self, ASSIGNMENT):

        self.__check_assignment(ASSIGNMENT)

        self.transition_matrix = self.__init_weights(self.cost_matrix)
        self.transition_matrix = self.__reshape_matrix()

        #Non essential - Ditch on implementation
        self.coordinates = ASSIGNMENT.coordinates
        self.a = 0.4
        self.ASSIGNMENT = {}

    def __reshape_matrix(self):
        stacked_transition = np.zeros([self.depots, self.nodes+1, self.nodes+1])
        for d in range(self.depots):
            single_transition = np.copy(self.transition_matrix)
            depot_list = list(range(self.depots))
            depot_list.remove(d)
            single_transition = np.delete(single_transition, depot_list, axis=0)
            single_transition = np.delete(single_transition, depot_list, axis=1)

            stacked_transition[d, :, :] = single_transition
        return stacked_transition

    def __check_assignment(self, ASSIGNMENT):
        try:
            self.type = ASSIGNMENT.type
        except AttributeError:
           raise AttributeError('The Assignment type should be specified. List of objectives is: {TSP, TSPTW}')

        try:
            self.index = ASSIGNMENT.index

            self.depots = 0
            self.nodes = 0

            for v in self.index.values():
                if v['type'] == 'depot':
                    self.depots += 1
                if v['type'] == 'delivery':
                    self.nodes += 1

            self.depot_list = list(range(self.depots))
            self.node_list = list(range(self.nodes + 1))

        except AttributeError:
           raise AttributeError('The Assignment index should be specified. A dictionary with depot, or node label for each entry ')

        try:
            self.cost_matrix = ASSIGNMENT.cost_matrix
        except AttributeError:
           raise AttributeError('The Assignment distance_matrix should be specified.')

        if self.type == 'TSPTW':
            for idx, v in self.index.items():
                if 'tw' in v:
                    if 'start' in v['tw']:
                        if not isinstance(v['tw']['start'], (float, int)):
                            raise ValueError('tw start attribute is the wrong type. Should be float or int timestamp !')
                    else:
                        self.index[idx]['tw']['start'] = -1

                    if 'end' in v['tw']:
                        if not isinstance(v['tw']['end'], (float, int)):
                            raise ValueError('tw start attribute is the wrong type. Should be float or int timestamp !')
                    else:
                        self.index[idx]['tw']['end'] = -1
                else:
                    self.index[idx]['tw'] = {'start': -1, 'end': -1}

            try:
                self.time_matrix = ASSIGNMENT.time_matrix
            except AttributeError:
                raise AttributeError('For TSPTW problems, the time_matrix should be specified.')

            try:
                self.cost_matrix = ASSIGNMENT.cost_matrix
            except AttributeError:
                raise AttributeError('The cost_matrix should be specified.')

    def __call__(self, ce_samples=100, batch=15, c1_0=10, theta=0.05):
        y = 9999999
        self.ASSIGNMENT = {'message': 'NO ASSIGNMENT FOUND', 'acc_energy': y}
        depot = 0

        for sample in range(ce_samples):
            t = sample/ce_samples
            c1 = 1 + (c1_0 - 1)*(1 - t)

            quantile = c1 / len(self.node_list)
            ASSIGNMENT, COST = self.__get_route_batch(batch)
            ROUTE_MAX, COST_MAX = self.__sort_routes(ASSIGNMENT, COST, y)

            if len(COST_MAX) > 1:
                theta_ = (COST_MAX[1] - COST_MAX[0]) / COST_MAX[0]
                if theta_ < theta:
                    quantile *= 1.5

            quantile_val = np.quantile(COST, quantile)
            if quantile_val < y:
                y = quantile_val

            OVERALL_SCORE = np.sum(COST)
            if OVERALL_SCORE > 0:
                self.transition_matrix *= (1-self.a)
                for idx_assign, assignment in enumerate(ROUTE_MAX):

                    if COST_MAX[0] < self.ASSIGNMENT['acc_energy']:
                        self.ASSIGNMENT = ROUTE_MAX[0]
                        print(self.ASSIGNMENT['acc_energy'], depot)

                    for idx, node_0 in enumerate(assignment[depot]['nodes']):
                        if idx > len(assignment[depot]['nodes'])-2:
                            break

                        if np.random.rand() > 0.9:
                            assignment[depot]['nodes'] = self.__local_search(assignment[depot]['nodes'], idx, size=4)

                        node_1 = assignment[depot]['nodes'][idx + 1]
                        self.transition_matrix[:, node_0, node_1] += self.a*1.0/len(ROUTE_MAX)

        return 'finished'

    def __sort_routes(self, assignment, cost, y):
        sort_cost_idx = np.argsort(cost)
        route_max = []
        cost_max = []

        for i in sort_cost_idx:
            if cost[i] < y:
                route_max.append(assignment[i])
                cost_max.append(cost[i])

        return route_max, cost_max

    def __local_search(self, x, point_idx, size=5):
        size += 2
        start = point_idx
        start = np.clip(start, 1, len(x)-1)
        end = np.clip(point_idx + size, 1, len(x)-1)

        partial_route = x[start:end]
        permutes = list(itertools.permutations(partial_route[1:-1]))
        score_list = []
        ops = 0
        for perm in permutes:
            score = 0
            proposal_partial_route = np.asarray(partial_route)
            proposal_partial_route[1:-1] = np.asarray(perm)

            for idx, val in enumerate(proposal_partial_route):
                ops += 1
                if idx < len(proposal_partial_route)-1:
                    score += self.cost_matrix[proposal_partial_route[idx], proposal_partial_route[idx+1]]

            score_list.append(score)
            if len(score_list) > 1:
                if score_list[-1] < score_list[0]:
                    break

        idx_min = np.argmin(score_list)
        best_perm = np.asarray(permutes[idx_min])
        partial_route[1:-1] = best_perm

        x[start:end] = partial_route

        return x

    def __get_route(self):
        ROUTE_ASSIGNMENT = {}
        ROUTE_ASSIGNMENT['acc_energy_depot'] = [0]*self.depots
        ROUTE_ASSIGNMENT['acc_energy'] = 0

        tm = np.copy(self.transition_matrix)

        for i in self.depot_list:
            ROUTE_ASSIGNMENT[i] = {'nodes': [0], 'energy': [0], 'trans_energy': list([0]*len(self.node_list))}

        # ITERATE OVER PATH NODES
        for step, node_nr in enumerate(self.node_list):
            transition_node_list = {}
            tm_temp = np.copy(tm)

            # Iterate over depots and expand routes by 1
            for d in self.depot_list:
                # Get current node for this depot
                current_node = ROUTE_ASSIGNMENT[d]['nodes'][-1]

                if current_node <= 0 and step > 0:
                    continue

                tm_temp[:, :, current_node] *= 0
                tm_temp[:, current_node, :] *= 0

                # Get transition probs and terminate if no path is available
                trans_probs = tm[d, current_node, :]
                forbidden_nodes = []

                for de in self.depot_list:
                    forbidden_nodes.append(ROUTE_ASSIGNMENT[de]['nodes'][-1])

                trans_probs[forbidden_nodes] = 0
                norm_probs = np.sum(trans_probs)

                if norm_probs == 0:
                    transition_node = -d
                    proposal_transitions_prob = 0
                    proposal_transitions_cost = 0
                else:
                    probs = trans_probs / norm_probs
                    transition_node = np.random.choice(self.node_list, size=1, p=probs)[0]

                    # Get score for this transition
                    proposal_transitions_prob = tm[d, current_node, transition_node]
                    proposal_transitions_cost = self.cost_matrix[current_node, transition_node] + 0.1*np.exp(0.5*len(ROUTE_ASSIGNMENT[d]['nodes']))

                # look for paths going to the same node
                if not transition_node in transition_node_list:
                    transition_node_list[transition_node] = [[d, current_node, transition_node, proposal_transitions_prob, proposal_transitions_cost]]
                else:
                    transition_node_list[transition_node].append([d, current_node, transition_node, proposal_transitions_prob, proposal_transitions_cost])
            tm = tm_temp
            ROUTE_ASSIGNMENT = self.__pick_convergent_route(ROUTE_ASSIGNMENT, transition_node_list)

        return ROUTE_ASSIGNMENT

    def __pick_convergent_route(self, ROUTE_ASSIGNMENT, transition_node_list):
        # UPDATE ROUTE ASSIGNMENT
        for t1 in transition_node_list:
            # Store transition costs
            energies = []
            for t2 in transition_node_list[t1]:
                energies.append(np.exp(-0.001*t2[3]))
            # If more vecs converge on the same node - probabilistic pick of vecs based on best transition
            if len(energies) > 1:
                choose_idx = np.random.choice(list(range(len(energies))), size=1, p=energies / np.sum(energies))[0]
                ROUTE_ASSIGNMENT[choose_idx]['nodes'].append(transition_node_list[t1][choose_idx][2])
                ROUTE_ASSIGNMENT[choose_idx]['energy'] += transition_node_list[t1][choose_idx][4]
                ROUTE_ASSIGNMENT['acc_energy_depot'][transition_node_list[t1][0][0]] += transition_node_list[t1][choose_idx][4]
                ROUTE_ASSIGNMENT[choose_idx]['trans_energy'][transition_node_list[t1][0][1]] = transition_node_list[t1][choose_idx][4]

            # If no controversies, pick the only one available
            else:
                ROUTE_ASSIGNMENT[transition_node_list[t1][0][0]]['nodes'].append(transition_node_list[t1][0][2])
                ROUTE_ASSIGNMENT[transition_node_list[t1][0][0]]['energy'] += transition_node_list[t1][0][4]
                ROUTE_ASSIGNMENT['acc_energy_depot'][transition_node_list[t1][0][0]] += transition_node_list[t1][0][4]
                ROUTE_ASSIGNMENT[transition_node_list[t1][0][0]]['trans_energy'][transition_node_list[t1][0][1]] = transition_node_list[t1][0][4]

        ROUTE_ASSIGNMENT['acc_energy'] = np.sum(ROUTE_ASSIGNMENT['acc_energy_depot'])
        return ROUTE_ASSIGNMENT

    def __get_route_batch(self, batch=1):
        route_batch = []
        acc_batch = []

        for _ in range(batch):
            ROUTE_ASSIGNMENT = self.__get_route()
            route_batch.append(ROUTE_ASSIGNMENT)
            acc_batch.append(ROUTE_ASSIGNMENT['acc_energy'])

        return route_batch, acc_batch

    def __init_weights(self, distance_matrix, distance_weights=True):
        transition_matrix = np.ones(np.shape(distance_matrix)) - np.eye(np.shape(distance_matrix)[0])
        transition_matrix /= (np.shape(distance_matrix)[0] - 1)

        if distance_weights:
            for i in range(np.shape(distance_matrix)[0]):
                for j in range(np.shape(distance_matrix)[1]):
                    transition_matrix[i, j] = np.exp(-distance_matrix[i, j])

            transition_matrix -= np.eye(np.shape(transition_matrix)[0])
            for i in range(np.shape(distance_matrix)[0]):
                transition_matrix[i, :] = transition_matrix[i, :] / np.sum(transition_matrix[i, :])

        return transition_matrix

    def display_route(self):
        del self.ASSIGNMENT['acc_energy']
        del self.ASSIGNMENT['acc_energy_depot']
        for idx, val in self.ASSIGNMENT.items():
            depot_idx = -val['nodes'][-1]

            coords = [[self.coordinates[depot_idx][0]], [self.coordinates[depot_idx][1]]]

            for node in val['nodes'][1:-1]:
                real_node = node+self.depots-1
                coords[0].append(self.coordinates[real_node][0])
                coords[1].append(self.coordinates[real_node][1])

            plt.plot(coords[0], coords[1], alpha=0.35)
            plt.scatter(coords[0], coords[1], s=40, alpha=0.85)

            for i in range(len(coords[0])):
                plt.text(coords[0][i], coords[1][i], '(' + str(i) + ',' + str(val['nodes'][i]) + ')')
        #print(self.transition_matrix)
        plt.show()

game = game.routeGame(1, 20, seed=200, geo='circle')
ps = Sample(game)
ps(batch=70, ce_samples=10)
ps.display_route()






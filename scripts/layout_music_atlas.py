"""Deterministic build-time packing. The browser never runs force layout."""
import hashlib
import math


def precompute_layout(network):
    import numpy as np
    from scipy.spatial import cKDTree
    nodes = sorted(network['nodes'], key=lambda n: n['id'])
    index = {n['id']: i for i, n in enumerate(nodes)}
    group_by_id = {g['id']: g for g in network['groups']}
    sizing = network['sizing']
    scores = np.log([n['centrality']['pageRank'] for n in nodes])
    normalized = (scores - scores.min()) / max(1e-12, np.ptp(scores))
    radii = sizing['minRadius'] + normalized * (sizing['maxRadius'] - sizing['minRadius'])
    centers = np.array([group_by_id[n['group']]['center'] for n in nodes], dtype=float)
    positions = np.zeros((len(nodes), 2))
    # Compact sunflower seeds; sorting by stable ID makes reordering irrelevant.
    for group in network['groups']:
        members = [index[n['id']] for n in nodes if n['group'] == group['id']]
        if not members:
            continue
        for j, i in enumerate(members):
            if group.get('background'):
                seed = int(hashlib.sha256(str(nodes[i]['id']).encode()).hexdigest()[:16], 16)
                rng = np.random.default_rng(seed)
                positions[i] = [rng.uniform(180, 3380), rng.uniform(180, 2420)]
                continue
            angle = j * math.pi * (3 - math.sqrt(5))
            radius = math.sqrt(j + .5) * 34
            positions[i] = centers[i] + radius * np.array([math.cos(angle), math.sin(angle)])
    anchors = positions.copy()
    # Region names must not overlap the packed nodes; only in-region springs are
    # used so long cross-region relationships cannot collapse the composition.
    local = [(index[e['source']], index[e['target']]) for e in network['edges']
        if e['kind'] in ['album', 'artist', 'sound', 'emotion', 'structure']]
    pairs = np.array(local, dtype=int).reshape(-1, 2)
    anchor_strength = np.array([.04 if group_by_id[n['group']].get('background') else .025 for n in nodes])[:, None]
    for iteration in range(280):
        force = (anchors - positions) * anchor_strength
        collision = cKDTree(positions).query_pairs(float(radii.max() * 2 + 20), output_type='ndarray')
        if len(collision):
            a, b = collision.T
            delta = positions[b] - positions[a]
            distance = np.maximum(np.linalg.norm(delta, axis=1), .001)
            required = radii[a] + radii[b] + 16
            magnitude = np.maximum(0, required - distance) * .38
            push = delta / distance[:, None] * magnitude[:, None]
            np.add.at(force, a, -push)
            np.add.at(force, b, push)
        if len(pairs):
            a, b = pairs.T
            delta = positions[b] - positions[a]
            distance = np.maximum(np.linalg.norm(delta, axis=1), .001)
            same_group = np.array([nodes[x]['group'] == nodes[y]['group'] for x, y in pairs])
            desired = np.where(same_group, 95, 900)
            pull = delta / distance[:, None] * ((distance - desired) * .005)[:, None]
            np.add.at(force, a, pull)
            np.add.at(force, b, -pull)
        positions += np.clip(force, -8, 8) * (1 - iteration / 380)
    # Final collision-only relaxation ensures readable thumbnails independent of
    # relationships. This remains build-time work, including for newly added IDs.
    for _ in range(120):
        collision = cKDTree(positions).query_pairs(float(radii.max() * 2 + 18), output_type='ndarray')
        if not len(collision):
            break
        a, b = collision.T
        delta = positions[b] - positions[a]
        distance = np.maximum(np.linalg.norm(delta, axis=1), .001)
        overlap = np.maximum(0, radii[a] + radii[b] + 12 - distance)
        if overlap.max(initial=0) < .1:
            break
        push = delta / distance[:, None] * (overlap * .5)[:, None]
        force = np.zeros_like(positions)
        np.add.at(force, a, -push)
        np.add.at(force, b, push)
        positions += force
    for i, node in enumerate(nodes):
        node['position'] = [round(float(v), 3) for v in positions[i]]
        node['radius'] = round(float(radii[i]), 3)
    for group in network['groups']:
        members = [n for n in nodes if n['group'] == group['id']]
        group['labelPosition'] = [group['center'][0], min((n['position'][1] - n['radius'] for n in members), default=group['center'][1]) - 65]
    world_width = max(3600, math.ceil(max(n['position'][0] + n['radius'] for n in nodes) + 100))
    world_height = max(2600, math.ceil(max(n['position'][1] + n['radius'] for n in nodes) + 130))
    network['layout'] = dict(method='build-time-spatial-packing', width=world_width, height=world_height,
        minNodeGap=12, motionAmplitude=28, edgeBudget=220, labelBudget=28, mobileLabelBudget=10,
        seed=811456, inputHash=hashlib.sha256(str([(n['id'], n['group']) for n in nodes]).encode()).hexdigest())
    return network


def precompute_style_layout(network):
    """Deterministic elliptical constellations, relaxed once during the build."""
    import numpy as np
    groups = network['styleView']['groups']
    for group in groups:
        members = sorted((n for n in network['nodes'] if n['styleGroup']==group['id']),
            key=lambda n:(n.get('artistIds',[]),n['id']))
        x,y,width,height=group['bounds']
        positions=[]
        golden_angle=math.pi*(3-math.sqrt(5))
        for index,node in enumerate(members):
            radius=math.sqrt((index+.5)/len(members))
            angle=index*golden_angle
            positions.append([x+width/2+radius*math.cos(angle)*(width-160)/2,
                y+height/2+40+radius*math.sin(angle)*(height-200)/2])
        positions=np.array(positions)
        radii=np.array([n['radius'] for n in members])
        from scipy.spatial import cKDTree
        for _ in range(100):
            pairs=cKDTree(positions).query_pairs(float(radii.max()*2+14),output_type='ndarray')
            if not len(pairs):break
            a,b=pairs.T;delta=positions[b]-positions[a]
            distance=np.maximum(np.linalg.norm(delta,axis=1),.001)
            overlap=np.maximum(0,radii[a]+radii[b]+12-distance)
            if overlap.max(initial=0)<.1:break
            push=delta/distance[:,None]*(overlap*.51)[:,None]
            force=np.zeros_like(positions);np.add.at(force,a,-push);np.add.at(force,b,push)
            positions+=force
        for node,position in zip(members,positions):
            node['stylePosition']=[round(float(v),3) for v in position]
        group['labelPosition']=[x+width/2,y+48]
    network['styleView']['method']='build-time-multilabel-style-regions'

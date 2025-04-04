# -*- coding: utf-8 -*-
import math
from copy import deepcopy
from collections import defaultdict
from typing import Dict, Union, List, Tuple, Optional, Set
from difflib import get_close_matches

# --- Node class definition ---
class Node:
    def __init__(self, item: str, needed: float, depth: int):
        self.item = item
        self.needed = needed
        self.produced = 0.0
        self.actual_produced_by_recipe = 0.0
        self.source = "unknown"
        self.recipe_details: Optional[Tuple[Dict[str, float], Dict[str, float]]] = None
        self.children: List['Node'] = []
        self.depth = depth

    def add_child(self, child: 'Node'): self.children.append(child)
    def __repr__(self): return f"Node({self.item}, needed={self.needed:.2f}, produced={self.produced:.2f}, actual_produced={self.actual_produced_by_recipe:.2f}, source={self.source}, depth={self.depth})"

# --- Global Variables / Helper Functions ---
resources = [
    ({"Log": 1}, {"Planks": 4}),
    ({"Planks": 2}, {"Stick": 4}),
    ({"Planks": 3, "Stick": 2}, {"Wooden Pickaxe": 1}),
]
_all_items_cache: Optional[List[str]] = None
_base_resources_cache: Optional[Set[str]] = None
def format_float(value: float) -> str:
    if abs(value) < 1e-9: return "0"
    if abs(value - round(value)) < 1e-9: return str(int(round(value)))
    else: return f"{value:.4f}".rstrip('0').rstrip('.')
def get_all_items() -> List[str]:
    global _all_items_cache
    if _all_items_cache is None:
        all_items = set().union(*[r[0].keys() for r in resources]).union(*[r[1].keys() for r in resources])
        _all_items_cache = sorted(list(all_items))
    return _all_items_cache
def get_base_resources() -> Set[str]:
    global _base_resources_cache
    if _base_resources_cache is None:
        all_items = set(get_all_items())
        all_outputs = set().union(*[r[1].keys() for r in resources])
        _base_resources_cache = all_items - all_outputs
    return _base_resources_cache

# --- calculate_resources / recurse ---
def calculate_resources(
    items: List[Tuple[str, float]],
    initial_available_resources: Dict[str, float] = None
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], Dict[str, float], List[Node]]:
    available_resources = defaultdict(float, initial_available_resources or {})
    aggregated_inputs = defaultdict(float)
    aggregated_outputs = defaultdict(float)
    aggregated_intermediates = defaultdict(float)
    tree_roots: List[Node] = []
    base_resources = get_base_resources()

    def recurse(
        item: str, qty: float, current_available_resources: Dict[str, float],
        indent: int, processing: Optional[set] = None, dependency_chain: List[str] = [],
        depth: int = 0
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], Dict[str, float], Node]:

        current_node = Node(item, qty, depth)

        if processing is None: processing = set()
        if qty <= 1e-9:
            current_node.source = "zero_needed"
            return defaultdict(float), defaultdict(float), defaultdict(float), current_available_resources, current_node

        if item in processing:
            current_node.source = "unresolved_loop"
            return {item: qty}, defaultdict(float), defaultdict(float), current_available_resources.copy(), current_node

        new_processing = processing.copy(); new_processing.add(item)
        new_dependency_chain = dependency_chain + [item]

        call_inputs = defaultdict(float)
        call_outputs = defaultdict(float)
        call_byproducts = defaultdict(float)
        resources_before_fulfillment = deepcopy(current_available_resources)
        resources_after_stock_use = deepcopy(resources_before_fulfillment)

        # --- Stock Use ---
        available_qty = resources_before_fulfillment.get(item, 0)
        used_from_stock = min(available_qty, qty)

        if used_from_stock > 1e-9:
            resources_after_stock_use[item] -= used_from_stock
            qty -= used_from_stock
            stock_node = Node(item, used_from_stock, depth + 1)
            stock_node.source = "stock"; stock_node.produced = used_from_stock
            current_node.add_child(stock_node)
            current_node.produced += used_from_stock

        if qty <= 1e-9:
            if not current_node.source or current_node.source == "unknown":
                current_node.source = "stock_only"
            return call_inputs, call_outputs, call_byproducts, resources_after_stock_use, current_node

        # --- Recipe Search ---
        routes = []
        for i, (recipe_inputs, recipe_outputs) in enumerate(resources):
            if item in recipe_outputs and recipe_outputs[item] > 1e-9:
                routes.append({"index": i, "inputs": recipe_inputs, "outputs": recipe_outputs})

        if routes:
            all_route_results = []
            resources_for_recipe_eval = resources_after_stock_use

            for route_idx, route_info in enumerate(routes):
                recipe_index = route_info["index"]
                recipe_inputs = route_info["inputs"]
                recipe_outputs = route_info["outputs"]
                route_total_inputs = defaultdict(float)
                route_total_byproducts = defaultdict(float)
                route_children_nodes_for_this_route = []
                possible_route = True
                sub_routes_count = 0

                if item not in recipe_outputs or recipe_outputs[item] <= 1e-9: possible_route = False; continue

                recipe_output_qty = recipe_outputs[item]
                scale_factor = math.ceil(qty / recipe_output_qty)

                # --- Evaluate Inputs for this Route ---
                for input_item, input_qty_per_recipe in recipe_inputs.items():
                    required_qty = input_qty_per_recipe * scale_factor
                    sub_inputs, sub_outputs, sub_byproducts, _, sub_node = recurse(
                        input_item, required_qty, resources_for_recipe_eval,
                        indent + 1, new_processing, new_dependency_chain,
                        depth=depth + 1
                    )
                    if input_item in sub_inputs and input_item not in base_resources:
                        if sub_inputs[input_item] >= required_qty - 1e-9: possible_route = False; break
                    for res, amount in sub_inputs.items(): route_total_inputs[res] += amount
                    for res, amount in sub_byproducts.items(): route_total_byproducts[res] += amount
                    route_children_nodes_for_this_route.append(sub_node)
                    if any(n.source.startswith("recipe_") for n in sub_node.children): sub_routes_count += 1

                if not possible_route: continue

                # --- Calculate Route Effects & Final State ---
                produced_target_item_qty = recipe_output_qty * scale_factor
                used_target_item_qty = qty
                excess_target_item_qty = produced_target_item_qty - used_target_item_qty
                if excess_target_item_qty > 1e-9: route_total_byproducts[item] += excess_target_item_qty
                for output_item, output_qty_per_recipe in recipe_outputs.items():
                    if output_item != item:
                        produced_byproduct_qty = output_qty_per_recipe * scale_factor
                        if produced_byproduct_qty > 1e-9: route_total_byproducts[output_item] += produced_byproduct_qty
                final_state_for_this_route = deepcopy(resources_for_recipe_eval)
                for res, amount in route_total_inputs.items():
                    if res in base_resources: final_state_for_this_route[res] -= amount
                for res, amount in route_total_byproducts.items(): final_state_for_this_route[res] += amount
                final_state_for_this_route[item] += used_target_item_qty
                final_state_for_this_route = defaultdict(float, {k:v for k,v in final_state_for_this_route.items() if v > 1e-9})

                # --- Score the route ---
                route_score = (sum(route_total_inputs.values()) * 1000) + sub_routes_count
                all_route_results.append({
                    "score": route_score, "inputs": route_total_inputs,
                    "outputs": {item: used_target_item_qty}, "byproducts": route_total_byproducts,
                    "available": dict(final_state_for_this_route), "recipe_index": recipe_index,
                    "children": route_children_nodes_for_this_route,
                    "actual_produced": produced_target_item_qty
                })

            # --- Optimal route selection ---
            if all_route_results:
                best_route_info = min(all_route_results, key=lambda x: x["score"])

                for res, amount in best_route_info["inputs"].items(): call_inputs[res] += amount
                for res, amount in best_route_info["outputs"].items(): call_outputs[res] += amount
                for res, amount in best_route_info["byproducts"].items(): call_byproducts[res] += amount
                resources_after_fulfillment = defaultdict(float, best_route_info["available"])

                current_node.source = f"recipe_{best_route_info['recipe_index']}"
                current_node.recipe_details = (resources[best_route_info['recipe_index']][0], resources[best_route_info['recipe_index']][1])
                current_node.produced += best_route_info["outputs"].get(item, 0)
                current_node.actual_produced_by_recipe = best_route_info["actual_produced"]
                current_node.children.extend(best_route_info["children"])

            else:
                current_node.source = "no_viable_route"
                call_inputs[item] += qty
                resources_after_fulfillment = resources_after_stock_use

        else:
            if item in base_resources:
                current_node.source = "base"
                current_node.produced = qty
                current_node.actual_produced_by_recipe = qty
                call_inputs[item] += qty
                resources_after_fulfillment = resources_after_stock_use
            else:
                current_node.source = "missing_recipe_or_base"
                call_inputs[item] += qty
                resources_after_fulfillment = resources_after_stock_use

        # --- Track Intermediate Consumption ---
        if item not in base_resources and current_node.source.startswith("recipe_") and current_node.produced > 1e-9 and depth > 0:
            aggregated_intermediates[item] += current_node.produced

        return call_inputs, call_outputs, call_byproducts, dict(resources_after_fulfillment), current_node


    # --- calculate_resources Main processing ---
    current_available_resources = deepcopy(available_resources)
    for item_name, item_qty in items:
        inputs, outputs, byproducts, current_available_resources_after, top_node = recurse(
            item_name, item_qty, current_available_resources, 0, processing=set(),
            depth=0
        )
        tree_roots.append(top_node)

        current_available_resources = current_available_resources_after
        for resource, amount in inputs.items(): aggregated_inputs[resource] += amount
        for resource, amount in outputs.items(): aggregated_outputs[resource] += amount

    final_inputs = dict(aggregated_inputs)
    final_outputs = dict(aggregated_outputs)
    final_available_resources = dict(current_available_resources)
    final_intermediates = dict(aggregated_intermediates)
    return final_inputs, final_outputs, final_available_resources, final_intermediates, tree_roots

# --- categorize_products ---
def categorize_products(
    inputs: Dict[str, float], outputs: Dict[str, float], final_available: Dict[str, float],
    intermediates_consumed: Dict[str, float], requested_items: List[str],
    initial_available: Dict[str, float]
) -> Dict[str, Dict[str, float]]:
    categories = {"intermediate": defaultdict(float), "finished": defaultdict(float), "byproduct": defaultdict(float)}
    requested_set = set(requested_items); base_resources = get_base_resources()
    initial_available_dd = defaultdict(float, initial_available)
    for item, amount in outputs.items():
        if item in requested_set and amount > 1e-9: categories["finished"][item] += amount
    for item, amount in intermediates_consumed.items():
        if amount > 1e-9: categories["intermediate"][item] += amount
    for item, final_amount in final_available.items():
        if final_amount <= 1e-9 or item in base_resources: continue
        finished_amount = categories["finished"].get(item, 0)
        if item not in categories["finished"]: categories["byproduct"][item] = final_amount
        else:
            excess_over_finished = final_amount - finished_amount
            if excess_over_finished > 1e-9: categories["byproduct"][item] = excess_over_finished
    return {k: {k2: v2 for k2, v2 in v.items() if v2 > 1e-9} for k, v in categories.items()}

# --- fuzzy_match_item ---
def fuzzy_match_item(item: str, all_items: List[str]) -> Union[List[str], None]:
    matches = get_close_matches(item.lower(), [i.lower() for i in all_items], n=3, cutoff=0.6)
    if not matches: return None
    item_lower_map = {i.lower(): i for i in all_items}
    return [item_lower_map[match] for match in matches]

# --- process_input ---
def process_input(
    input_str: str, initial_available_resources: Dict[str, float] = None
) -> Union[Tuple[Dict[str, float], Dict[str, Dict[str, float]], Dict[str, float], List[Node]], str]:
    all_items = get_all_items(); items_to_calculate = []; requested_item_names = []
    initial_available_dict = initial_available_resources or {}
    try:
        for item_input in input_str.split(';'):
            item_input = item_input.strip();
            if not item_input: continue
            parts = [p.strip() for p in item_input.split(',')]; item = parts[0]; number = 1.0
            if len(parts) == 2:
                try: number = float(parts[1]); assert number > 0
                except: raise ValueError(f"Invalid quantity for {item}")
            elif len(parts) > 2: raise ValueError(f"Invalid format: {item_input}")
            if item not in all_items:
                matched = fuzzy_match_item(item, all_items);
                if not matched: return f"Item '{item}' not found."
                print(f"Assuming '{item}' meant '{matched[0]}'"); item = matched[0]
            items_to_calculate.append((item, float(number))); requested_item_names.append(item)
        if not items_to_calculate: return "No valid items entered."
        final_inputs, final_outputs, final_available, final_intermediates, trees = calculate_resources(items_to_calculate, initial_available_dict)
        categorized = categorize_products(final_inputs, final_outputs, final_available, final_intermediates, requested_item_names, initial_available_dict)
        return dict(final_inputs), categorized, dict(final_available), trees
    except ValueError as e: return f"Input error: {str(e)}"
    except Exception as e: import traceback; print(f"An unexpected error occurred: {traceback.format_exc()}"); return f"An unexpected error occurred: {str(e)}."

# --- print_recipe_tree ---
def print_recipe_tree(nodes: List[Node]):
    print("\n--- Recipe Tree ---");
    if not nodes: print("  (No tree generated)"); return
    def print_node(node: Node, prefix: str = "", is_last: bool = True):
        connector = "└─ " if is_last else "├─ "; line = f"{prefix}{connector}{node.item} (Needed: {format_float(node.needed)}"
        source = node.source or "unknown"
        if source.startswith("recipe_") and node.actual_produced_by_recipe > 1e-9: line += f", Produced: {format_float(node.actual_produced_by_recipe)}"
        elif source == "stock" and node.produced > 1e-9: line += f", Used from Stock: {format_float(node.produced)}"
        line += f") [{source}]"; print(line)
        new_prefix = prefix + ("    " if is_last else "│   ")
        def sort_key(child: Node): src = child.source or ''; return (0 if src=='stock' else 1 if src=='base' else 2 if src.startswith('recipe_') else 3, child.item)
        sorted_children = sorted(node.children, key=sort_key)
        for i, child in enumerate(sorted_children): print_node(child, new_prefix, i == len(sorted_children) - 1)
    for root in nodes:
        print(f"\nTree for: {root.item} (Needed: {format_float(root.needed)}) [{root.source or 'unknown'}]")
        def sort_key_root(child: Node): src = child.source or ''; return (0 if src=='stock' else 1 if src=='base' else 2 if src.startswith('recipe_') else 3, child.item)
        sorted_children = sorted(root.children, key=sort_key_root)
        for i, child in enumerate(sorted_children): print_node(child, "", i == len(sorted_children) - 1)

# --- main ---
def main() -> None:
    available_resources_main = defaultdict(float)
    print("Welcome! Enter items and quantities (e.g., 'Planks, 5; Stick, 2').")
    get_all_items(); get_base_resources()
    print("Available items:", ", ".join(get_all_items())); print("Base resources:", ", ".join(sorted(list(get_base_resources())))); print("Type 'quit' to exit.")
    while True:
        user_input = input("\nEnter items: ").strip();
        if user_input.lower() == 'quit': break;
        if not user_input: continue
        result = process_input(user_input, dict(available_resources_main))
        if isinstance(result, str): print(f"Error: {result}")
        else:
            inputs, categorized, available, trees = result
            print_recipe_tree(trees); print("\n--- Calculation Result ---"); print("\nTotal base resources needed:")
            base_found = False;
            for res, amt in sorted(inputs.items()):
                if res in get_base_resources(): print(f"  {res}: {format_float(math.ceil(amt))}"); base_found = True
            if not base_found: print("  None")
            print("\nOutputs:"); out_cat = False
            if categorized.get("finished"): out_cat = True; print("  Finished products (Requested):"); [print(f"    {res}: {format_float(amt)}") for res, amt in sorted(categorized["finished"].items())]
            if categorized.get("intermediate"): out_cat = True; print("  Intermediate products (Crafted & Consumed):"); [print(f"    {res}: {format_float(amt)}") for res, amt in sorted(categorized["intermediate"].items())]
            if categorized.get("byproduct"): out_cat = True; print("  Byproducts / Excess (Remaining non-base):"); [print(f"    {res}: {format_float(amt)}") for res, amt in sorted(categorized["byproduct"].items())]
            if not out_cat and not inputs: print("  No products generated or resources needed/remaining.")
            elif not out_cat and inputs: print("  Only base inputs consumed, no specific products generated or remaining.")
            available_resources_main = defaultdict(float, available); print("\nUpdated available resources for next calculation:")
            has_avail = False;
            for item, amount in sorted(available_resources_main.items()):
                if amount > 1e-9: print(f"  {item}: {format_float(amount)}"); has_avail = True
            if not has_avail: print("  None")
        print("-" * 30)
    print("Exiting program.")

if __name__ == "__main__": main()

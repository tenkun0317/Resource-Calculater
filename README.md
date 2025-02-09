# Resource-Calculater
This is a program that calculates the amount of resources needed. <br>
A dictionary called resources is needed in a file called resources.py. (The name can be changed internally.)

## Example of how to write a `resources` dictionary
Shown below is an example of a dictionary that defines a recipe for a resource. <br>
This dictionary defines the product, the input materials required for its manufacture, and the output materials produced.
```
resources = {
    "Wood": [
        ({"Log": 4}, {"Wood": 3})
    ],
    "Planks": [
        ({"Log": 1}, {"Planks": 4}),
        ({"Wood": 1}, {"Planks": 4})
        ],
    "Stick": [
        ({"Planks": 2}, {"Stick": 4})
    ],
    "Wooden Pickaxe": [
        ({"Planks": 3,"Stick": 2}, {"Wooden Pickaxe": 1})
    ],
    "Ladder": [
        ({"Stick": 7}, {"Ladder": 3})
    ]
}
```

### Meaning of each key and value
- Key: The name of the product (e.g., `Wood`, `"Planks"`, `"Stick"`, `"Wooden Pickaxe"`, `"Ladder"`).
- Value: a list, where each element is a tuple.
- First element of the tuple: a dictionary of input materials needed to create the product.
- Second element of the tuple: a dictionary representing the output product to be created.

For example, in the case of `Wooden Pickaxe`, the product name is `Wooden Pickaxe`, the input materials are three `Planks` and two `Stick`, and the output product is one `Wooden Pickaxe`. <br>
In this situation, there are two recipes for making a `planks`. In this case, two routes are calculated, and the best route is the route with the least number of resources required, and the second best route is the route with the least number of routes to go through. <br>
You may have any number of both inputs and outputs.

Preferably, the product name and the first output product should be the same.

## Features to be added
- Display of possible productions from the name and number of resources
- Display list of recipes from resources
- Display list of recipes for products
- Optional recipe tree file output

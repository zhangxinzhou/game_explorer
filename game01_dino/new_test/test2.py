from ray import tune


# 1. Define an objective function.
def objective(config, checkpoint_dir=None):
    score = config["a"] ** 2 + config["b"]
    return {"score": score}


# 2. Define a search space.
search_space = {
    "a": tune.grid_search([0.001, 0.01, 0.1, 1.0]),
    "b": tune.choice([1, 2, 3]),
}

# 3. Start a Tune run and print the best result.
analysis = tune.run(objective, config=search_space, resources_per_trial={'gpu': 1})
print(analysis.get_best_config(metric="score", mode="min"))

# Variables
RECIPES_DIR = recipes
TEMPLATES_DIR = templates
GENERATED_DIR = $(TEMPLATES_DIR)/recipes
STATIC_DIR = static

PYTHON = python3
SCRIPT = generate_recipe.py
TEMPLATE = $(TEMPLATES_DIR)/recipe.html

# Default target to build all recipes
all: $(patsubst $(RECIPES_DIR)/%.md, $(GENERATED_DIR)/%.html, $(wildcard $(RECIPES_DIR)/*.md))

# Create the generated directory if it doesn't exist
$(GENERATED_DIR):
	mkdir -p $(GENERATED_DIR)

# Markdown to HTML rule
$(GENERATED_DIR)/%.html: $(RECIPES_DIR)/%.md $(GENERATED_DIR)
	@if [ -f $(RECIPES_DIR)/$*.jpg ]; then \
		IMAGE=$(RECIPES_DIR)/$*.jpg; \
	else \
		IMAGE=""; \
	fi; \
	if [ -n "$$IMAGE" ]; then \
		$(PYTHON) $(SCRIPT) $< $@ $(TEMPLATE) $$IMAGE; \
	else \
		$(PYTHON) $(SCRIPT) $< $@ $(TEMPLATE); \
	fi;

# Clean generated files
clean:
	rm -f $(GENERATED_DIR)/*.html
	rm -f $(STATIC_DIR)/images/*.jpg
	rm -f recipes.db


"""DeepInfra AI generation for Atlas Map Forge (fork extension).

Turns a text prompt into a playable Spring map: a grayscale heightmap (in
elmos) and a top-down RGB texture, ready to be injected into the existing
build pipeline.

Usage:
    from atlasforge.ai import DeepInfraGenerator

    gen = DeepInfraGenerator()
    hm, tex = gen.generate_terrain("volcanic islands", size=(16, 8))
"""

from .generator import DeepInfraGenerator, DeepInfraError, DEFAULT_MODEL

__all__ = ["DeepInfraGenerator", "DeepInfraError", "DEFAULT_MODEL"]

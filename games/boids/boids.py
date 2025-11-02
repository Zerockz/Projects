import pygame
from pygame.math import Vector2
import random
from CLASSES import *

# Initialize Pygame and create objects here
pygame.init()
screen = pygame.display.set_mode((800, 600))

boids = [Boid((random.randint(0, 800), random.randint(0, 600)), (random.randint(-2, 2), random.randint(-2, 2))) for _ in range(100)]
hoiks = [Hoik((random.randint(0, 800), random.randint(0, 600)), (random.randint(-2, 2), random.randint(-2, 2))) for _ in range(5)]
obstacles = [Obstacle((random.randint(0, 800), random.randint(0, 600))) for _ in range(10)]

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((0, 0, 0))

    for boid in boids:
        boid.update(boids, hoiks,obstacles,  screen.get_width(), screen.get_height())
        boid.draw(screen)

    for hoik in hoiks:
        hoik.update(boids, screen.get_width(), screen.get_height())
        hoik.draw(screen)

    for obstacle in obstacles:
        obstacle.draw(screen)

    pygame.display.flip()

pygame.quit()

# config.py

"""file containing constants as screen width, height, gravity etc
"""
import pygame
screen_width= 800
screen_height= 600
screen = pygame.display.set_mode([screen_width, screen_height])



gravity= 1





# Assigns the inputs and direction of the bullet
player1_controls = {"left": pygame.K_a, "right": pygame.K_d, "forward": pygame.K_w, "shoot": pygame.K_s, "direction": "positive"}
player2_controls = {"left": pygame.K_LEFT, "right": pygame.K_RIGHT, "forward": pygame.K_UP, "shoot": pygame.K_DOWN, "direction": "negative"}




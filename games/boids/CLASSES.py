import pygame
from pygame.math import Vector2

class DrawableObject:
    def __init__(self, position, velocity):
        self.position = Vector2(position)
        self.velocity = Vector2(velocity)

    def draw(self, screen):
        pass

class MovingObject(DrawableObject):
    def __init__(self, position, velocity):
        super().__init__(position, velocity)

    def update(self):
        self.position += self.velocity

class Boid(MovingObject):
    def __init__(self, position, velocity):
        super().__init__(position, velocity)
        self.flockmates = []

    def draw(self, screen):
        pygame.draw.circle(screen, (255, 255, 255), (int(self.position.x), int(self.position.y)), 2)

    def update(self, boids, hoiks, obstacles, screen_width, screen_height):
        # Update flockmates
        self.flockmates = [boid for boid in boids if self != boid and self.position.distance_to(boid.position) < 50]

        # Rule 1: Boids steer towards the average position of local flockmates
        if self.flockmates:
            avg_position = sum((boid.position for boid in self.flockmates), Vector2()) / len(self.flockmates)
            self.velocity += (avg_position - self.position) * 0.01

        # Rule 2: Boids attempt to avoid crashing into other boids
        for boid in self.flockmates:
            if boid.position.distance_to(self.position) < 20:
                self.velocity += (self.position - boid.position) * 0.01

        # Rule 3: Boids steer towards the average heading of local flockmates
        if self.flockmates:
            avg_heading = sum((boid.velocity for boid in self.flockmates), Vector2()) / len(self.flockmates)
            self.velocity += (avg_heading - self.velocity) * 0.01

        # Rule 4: Boids avoid the edges of the screen
        margin = 50
        if self.position.x < margin:
            self.velocity.x += 0.1
        elif self.position.x > screen_width - margin:
            self.velocity.x -= 0.1

        if self.position.y < margin:
            self.velocity.y += 0.1
        elif self.position.y > screen_height - margin:
            self.velocity.y -= 0.1

        #Limit the speed
        min_speed= 0
        max_speed = 0.3
        if self.velocity.length() > min_speed:
            self.velocity.scale_to_length(max_speed)
        
        #Boids avoid hoiks
        for hoik in hoiks:
            if self.position.distance_to(hoik.position) < 50:
                repulsion_vector = self.position - hoik.position
                repulsion_vector.normalize_ip()
                self.velocity += repulsion_vector * 0.1
        
        #Boids avoid obstacles
        for obstacle in obstacles:
            if self.position.distance_to(obstacle.position) < 50:
                avoidance_vector = self.position - obstacle.position
                avoidance_vector.normalize_ip()
                self.velocity += avoidance_vector * 0.1

        super().update()

class Hoik(MovingObject):
    def __init__(self, position, velocity):
        super().__init__(position, velocity)

    def draw(self, screen):
        pygame.draw.circle(screen, (255, 0, 0), (int(self.position.x), int(self.position.y)), 2)

    def update(self, boids, screen_width, screen_height):
        # Hoiks will try to eat the boids
        for boid in boids:
            if self.position.distance_to(boid.position) < 20:
                self.velocity += (boid.position - self.position) * 0.01
                boids.remove(boid) 

        #chase boids
        if boids:
            closest_boid = min(boids, key=lambda boid: self.position.distance_to(boid.position))
            self.velocity += (closest_boid.position - self.position) * 0.01

        #limit speed
        max_speed = 0.3
        if self.velocity.length() > max_speed:
            self.velocity.scale_to_length(max_speed)

        super().update()

class Obstacle(DrawableObject):
    def __init__(self, position):
        super().__init__(position, (0, 0))

    def draw(self, screen):
        pygame.draw.rect(screen, (0, 255, 0), pygame.Rect(int(self.position.x), int(self.position.y), 10, 10))


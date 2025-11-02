import pygame
from config import *
import math


class Launch:
    """Class for launching the game

    """


    def main():
        """main method to start the game
        initializes pygame, sets up game window creats game objects,
        creates the sprite groups, adds,draws and updates them 
        runs the game loop.

        closes the game"""

        pygame.init()

        screen = pygame.display.set_mode((screen_width, screen_height))
        pygame.display.set_caption("Space Battle")

        clock = pygame.time.Clock()
        running = True


        obstacles= pygame.sprite.Group()
        fuel_barrels= pygame.sprite.Group()
        player_sprites = pygame.sprite.Group()
        bullet_group = pygame.sprite.Group()



        player1 = Player((100, 350), player1_controls)
        player2 = Player((600, 300), player2_controls)


        obstacles.add(Obstacle((400,200), (50,150),("gray")))
        fuel_barrels.add(Fuelbarrel((200,250)))
        fuel_barrels.add(Fuelbarrel((500,250)))
        player_sprites.add(player1)
        player_sprites.add(player2)

        
        font = pygame.font.Font(None, 36)  

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            screen.fill(("white"))

            # Update player and bullet sprites
            player_sprites.update(bullet_group, player_sprites, fuel_barrels,obstacles)
            bullet_group.update()

            # Draw player and bullet sprites
            player_sprites.draw(screen)
            bullet_group.draw(screen)
            fuel_barrels.draw(screen)
            obstacles.draw(screen)

            # Render and blits the scores and fuel counter for player 1 and 2
            score_p1 = font.render(f"Player 1 Score: {player1.score}", True, ("blue"))
            screen.blit(score_p1, (10, 10))

            fuel_text_p1 = font.render(f"Player 1 Fuel: {player1.fuel}", True, ("blue"))
            screen.blit(fuel_text_p1, (10, 50))

            score_p2 = font.render(f"Player 2 Score: {player2.score}", True, ("red"))
            screen.blit(score_p2, (screen_width - score_p2.get_width() - 10, 10))

            fuel_text_p2 = font.render(f"Player 2 Fuel: {player2.fuel}", True, ("red"))
            screen.blit(fuel_text_p2, (screen_width - fuel_text_p2.get_width() - 10, 50))

            pygame.display.flip()
            clock.tick(60)  # 60 FPS

        pygame.quit()








class Spaceship(pygame.sprite.Sprite):
    """parent class that inherits from sprite
    """


    def __init__(self, position, angle=0):
        """
        Initialize the ship

        Args:
            position: position of the spaceship as (x, y) tuple
            angle: Initial angle of the spaceship
        """
        super().__init__()
        self.original_image = pygame.image.load("spaceship2.png").convert_alpha()
        self.scaled_image = pygame.transform.scale(self.original_image, (70,70))
        self.image= self.scaled_image
        self.rect = self.image.get_rect()
        self.position = pygame.math.Vector2(position)
        self.angle = angle
        self.score=0
        self.angular_speed=0
        self.thrust_power=0.1
        self.velocity= pygame.math.Vector2(0,0)

    def rotate(self, delta_angle):
        """Rotates the ship.
        
        Args:
            delta_angle (float): Amount to rotate the spaceship in degrees."""
        
        self.angular_speed += delta_angle
        self.angle += self.angular_speed
        self.image = pygame.transform.rotate(self.scaled_image, self.angle-90)
        self.rect = self.image.get_rect(center=self.rect.center)

    def move_forward(self, thrust_power):
        """Moves the ship forward with the specified thrust power."""
        thrust_direction = pygame.math.Vector2(math.cos(math.radians(self.angle)), -math.sin(math.radians(self.angle)))
        self.velocity += thrust_direction * thrust_power
        self.position += self.velocity

        


    def update(self):
         pass
        

    

class Player(Spaceship):
    """Class representing a player spaceship inherits from Spaceship
    """

    def __init__(self, position, controls):
        """
        Initialize 

        Args:
            position: Initial position of the player ship as (x, y) tuple
            controls: Dictionary containing control mappings for the player
        """

        super().__init__(position)
        self.cooldown = 0
        self.last_shot = 30
        self.controls = controls
        self.fuel = 300 
        self.respawn_point= position

    def respawn(self):
        """respawns player ,refuels and removes a point"""

        self.position= pygame.math.Vector2(self.respawn_point)
        self.rect.center=self.position
        self.fuel=300
        self.score -=1
        self.velocity= (0,0)

    

    

    def Boundary_Check(self, screen_width, screen_height):
        """checks if the ship is out of bounds, respawns and refuels"""

        if self.rect.y >= screen_height or self.rect.y <= 0 or self.rect.x >= screen_width or self.rect.x <= 0:
            self.respawn()
            
            self.fuel=300


    def update(self, bullet_group, player_sprites, fuel_barrels, obstacles):
        """update method to handle logic such as collision movement and gravity
        and shooting cooldown"""
        self.cooldown += 1
        self.Boundary_Check(screen_width, screen_height)
        self.position.y += gravity
        self.rect.center = self.position
        if self.angular_speed !=0:
            self.angular_speed -= 2*(1 if self.angular_speed>0 else -1)
            if abs(self.angular_speed)<0.2:
                self.angular_speed=0
        self.angle += self.angular_speed
        self.image = pygame.transform.rotate(self.image, self.angular_speed)  # Rotate the ship
        


        



        # Check for collisions with bullets add point if target hit
        self.bullet_collisions = pygame.sprite.spritecollide(self, bullet_group, False)
        for bullet in self.bullet_collisions:
            if bullet.owner != self:
                self.respawn()  
                self.fuel = 300
                bullet.kill()
                bullet_owner= bullet.owner
                bullet_owner.score +=1
            

        #Check for collisions with spaceships respawns if hit
        self.enemy_collisions= pygame.sprite.spritecollide(self, player_sprites, False)
        for enemy in self.enemy_collisions:
            if enemy != self:
                self.respawn()

        #Check for collision with fuel barrels refuels if hit
        self.fuel_collisions= pygame.sprite.spritecollide(self,fuel_barrels,True)
        for fuel_barrels in self.fuel_collisions:
            self.fuel=300

        # Collisions with obstacle
        self.obstacle_collisions = pygame.sprite.spritecollide(self, obstacles, False)
        for obstacles in self.obstacle_collisions:
            self.respawn()


        #collisions between bullet and obstacle removes the bullet upon hit
        self.bullet_obstacle_collisions= pygame.sprite.groupcollide(bullet_group,obstacles,True,False)
        for bullet in self.bullet_obstacle_collisions:
            bullet.kill()
        
        
        if self.fuel > 0:
            keys = pygame.key.get_pressed()
            if keys[self.controls["left"]]:
                self.rotate(-0.05)
            if keys[self.controls["right"]]:
                self.rotate(0.05)
            if self.cooldown >= self.last_shot:
                if keys[self.controls["shoot"]]:
                    bullet_direction = self.controls["direction"]
                    bullet_pos = self.rect.centerx, self.rect.centery
                    bullet = Bullet(*bullet_pos, bullet_direction, self)
                    bullet_group.add(bullet)
                    self.cooldown = 0
            if keys[self.controls["forward"]]:
                self.move_forward(0.1)
                self.fuel -= 1 
                self.position.y -= gravity
                if self.fuel < 0:
                    self.fuel = 0
            """movement of the ship stops all inputs if fuel runs out
            a cooldown is implemented on shooting to stop spamming
            bullet logic like direction and position implemented
            gravity is cancelled if moving """




class Bullet(pygame.sprite.Sprite):
    """Bullet projectile class"""

    def __init__(self, x, y, direction, owner):
        """
        Initialize the program

        Args:
            x: Initial x-coordinate of the bullet
            y: Initial y-coordinate of the bullet
            direction: Direction of the bullet in positive or negative x direction
            owner: Object that owns the bullet
        """

        super().__init__()
        self.original_image = pygame.image.load("bullet2.png").convert_alpha()
        self.scaled_image = pygame.transform.scale(self.original_image, (40, 40))
        self.image = self.scaled_image
        self.rect = self.image.get_rect()
        self.rect.center = [x, y]
        self.direction=direction
        self.owner= owner

    def update(self):
        """handles bullet logic"""

        if self.direction=="positive":
            self.rect.x += 5
        else:
            self.rect.x -=5

    


class Obstacle(pygame.sprite.Sprite):
    """obstacle class"""

    def __init__(self,position, size, color):
        """
        Initialize

        Args:
            position: position of the obstacle as (x, y) tuple
            size: Size of the obstacle as (width, height) tuple
            color: Color
        """

        super().__init__()
        self.image= pygame.Surface(size)
        self.image.fill(color)
        self.rect= self.image.get_rect(topleft=position)




class Fuelbarrel(Obstacle):
    """fuelbarrel class child class of obstacle
    """
    def __init__(self,position):
        """
        Initialize

        Args:
            position: Initial position as (x, y) tuple
            """

        super().__init__(position,(40,40),("green"))
        

import pygame
import sys
from city_graph import grid, ROWS, COLS

class UI:
    def __init__(self):
        self.width  = 600
        self.height = 600
        self.fps    = 60
        self.title  = "CityMind - Urban Intelligence System"
        self.cell_size = 30
        self.BLACK  = (0, 0, 0)
        self.WHITE  = (255, 255, 255)
        self.GRAY   = (40, 40, 40)

        self.CELL_COLORS = {
            "empty":       (200, 200, 200),
            "hospital":    (255, 80,  80),
            "school":      (80,  80,  255),
            "industrial":  (255, 200, 50),
            "residential": (100, 200, 100),
        }

    def draw_grid(self, screen):
        for row in range(ROWS):
            for col in range(COLS):
                cell = grid[row][col]
                color = self.CELL_COLORS.get(cell["type"], (200, 200, 200))
                rect = (col * self.cell_size, row * self.cell_size, self.cell_size - 1, self.cell_size - 1)
                pygame.draw.rect(screen, color, rect)

    def game(self):
        pygame.init()
        screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(self.title)
        clock = pygame.time.Clock()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()

            screen.fill(self.GRAY)
            self.draw_grid(screen)
            pygame.display.flip()
            clock.tick(self.fps)

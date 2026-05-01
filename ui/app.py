import pygame
import sys

# --- Settings ---
WIDTH, HEIGHT = 900, 700
FPS = 60
TITLE = "CityMind - Urban Intelligence System"

# --- Colors ---
BLACK  = (0, 0, 0)
WHITE  = (255, 255, 255)
GRAY   = (40, 40, 40)

def game():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()

    while True:
        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

        # Draw
        screen.fill(GRAY)

        # Placeholder text
        font = pygame.font.SysFont(None, 48)
        text = font.render("CityMind", True, WHITE)
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, HEIGHT // 2 - 24))

        pygame.display.flip()
        clock.tick(FPS)
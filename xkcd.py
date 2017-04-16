import numpy as np
from vispy import app, gloo
from vispy import scene
from scipy import misc
from scipy import interpolate
from scipy.ndimage import filters
import sys
import os

class Canvas(app.Canvas):

    VERTEX_SHADER_CODE = """

        attribute vec2 position;
        attribute vec2 uv_texture;

        varying vec2 uv;

        void main() {
            uv = vec2(uv_texture.x, 1.0 - uv_texture.y);
            gl_Position = vec4(position, 0.0, 1.0);
        }
    """

    FRAGMENT_SHADER_CODE = """
        uniform sampler2D noise;
        uniform sampler2D img;
        uniform float strength;

        uniform int width;
        uniform int hight;

        varying vec2 uv;

        vec4 color(float dx, float dy) {
            vec2 UV = uv + vec2(dx, dy);
            return texture2D(img, UV + strength*2*(texture2D(noise, UV).xy - 0.5)); // again: vispy dosnt support GL_RGB_32F
        }

        void main() {
            float dx = 0.33/width;
            float dy = 0.33/hight;

            vec4 c0 = color(-dx, dy);
            vec4 c1 = color(0.0, dy);
            vec4 c2 = color(dx, dy);

            vec4 c3 = color(-dx, 0.0);
            vec4 c4 = color(0.0, 0.0);
            vec4 c5 = color(dx, 0.0);

            vec4 c6 = color(-dx, -dy);
            vec4 c7 = color(0.0, -dy);
            vec4 c8 = color(dx, -dy);

            vec4 c = (c0 + 2*c1 + c2 + 2*c3 + 4*c4 + 2*c5 + c6 + 2*c7 + c8) / 16.0;
            gl_FragColor = c;
        }
    """

    def __init__(self, file_name, strength, size, show=True, output_file_name="screen.png"):
        app.Canvas.__init__(self, keys='interactive', size=(800, 600))

        if type(file_name) == str:
            self.title = "xkcd_style showing '" + file_name + "'"
        else:
            self.title = "xkcd_style"

        self.strength, self.noise_size, self.output_file_name = strength, size, output_file_name

        def create_vertecies(dim):
            vertecies_data = np.zeros( 6, dtype=[('position', np.float32, 2), ('uv_texture', np.float32, 2)])
            vertecies_data['position'] = np.array([(-dim, -dim), (dim, -dim), (dim, dim),
                                            (-dim, -dim), (dim, dim), (-dim, dim)], np.float32)
            vertecies_data['uv_texture'] = np.array([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0),
                                            (0.0, 0.0), (1.0, 1.0), (0.0, 1.0)], np.float32)
            return gloo.VertexBuffer(vertecies_data)

        self.vertecies = create_vertecies(0.8)
        self.render_vertecies = create_vertecies(1.0)

        if type(file_name) == str:
            self.input_texture_data = (misc.imread(file_name).astype(np.float32))/255.0
        else:
            self.input_texture_data = file_name
        self.img_w, self.img_h, self.img_c = self.input_texture_data.shape
        print("self.input_texture_data.shape = %s" % (self.input_texture_data.shape,))
        self.input_texture = gloo.Texture2D(self.input_texture_data, interpolation='linear', resizable=False)
        #self.noise_texture_data = np.random.normal(size=(size, size))
        #xy = np.linspace(0, 1, size, np.float32)
        #self.noise_interp_func = interpolate.interp2d(xy, xy, self.noise_texture_data, kind="cubic")
        #w, h, c = self.input_texture_data.shape
        #self.noise_texture_real_data = self.noise_interp_func(np.linspace(0, 1, w, np.float32),
        #                                            np.linspace(0, 1, h, np.float32)).astype(np.float32)
        x, y = np.meshgrid(np.linspace(0, 1, self.img_w, np.float32), np.linspace(0, 1, self.img_h, np.float32))
        r = np.sqrt(x**2 + y**2)
        l = 1.0/size
        self.noise_texture_real_data = np.zeros((self.img_w, self.img_h, 2))
        # unvortunatly vispy dosent seem to suport GL_RGB_32F format for textures so I am pulling some strings
        self.noise_texture_real_data[:,:,0] = 0.5*np.sin(2*np.pi* r/l) + 0.5
        self.noise_texture_real_data[:,:,1] = 0.5*np.cos(2*np.pi* r/l) + 0.5
        self.noise_texture = gloo.Texture2D(self.noise_texture_real_data.astype(np.float32),
                                    interpolation='linear', resizable=False)

        self.fbo_tbo = gloo.Texture2D(shape=(self.img_w, self.img_h, 4))
        self.fbo = gloo.FrameBuffer(self.fbo_tbo)

        self.program = gloo.Program(Canvas.VERTEX_SHADER_CODE, Canvas.FRAGMENT_SHADER_CODE)
        self.program.bind(self.vertecies)
        self.program['noise'] = self.noise_texture
        self.program['img'] = self.input_texture
        self.program['strength'] = strength/100
        self.program['width'] = self.physical_size[0]
        self.program['hight'] = self.physical_size[1]

        self.blend_func = ('src_alpha', 'zero')

        gloo.set_clear_color((1.0, 1.0, 1.0, 0.0))
        gloo.set_state(blend=True, blend_func=self.blend_func)
        gloo.set_viewport(0, 0, self.physical_size[0], self.physical_size[1])

        self.timer = None
        if show:
            self.timer = app.Timer('auto', connect=self.on_timer, start=True)
            self.show()

    def on_timer(self, event):
        self.update()

    def on_mouse_wheel(self, event):
        self.strength += event.delta[1]*np.log(1 + np.abs(self.strength))/15
        self.program['strength'] = self.strength/100
        self.update()

    def on_resize(self, event):
        gloo.set_viewport(0, 0, event.physical_size[0], event.physical_size[1])

    def on_draw(self, event):
        try:
            gloo.set_state(blend=True, blend_func=self.blend_func)
            gloo.clear(color=True, depth=True)

            self.program.draw('triangles')
        except Exeption as e:
            print("Errror noted", e)

    def render_img(self):
        with self.fbo:
            gloo.set_clear_color('white')
            gloo.set_state(blend=True, blend_func=self.blend_func)
            gloo.clear(color=True, depth=True)
            gloo.set_viewport(0, 0, self.img_w, self.img_h)

            self.program['strength'] = self.strength/100
            self.program['width'] = self.img_w
            self.program['hight'] = self.img_h
            self.program.bind(self.render_vertecies)
            self.program.draw('triangles')

            img = self.fbo.read()

        gloo.set_viewport(0, 0, self.physical_size[0], self.physical_size[1])
        gloo.set_state(blend=True, blend_func=self.blend_func)
        self.program.bind(self.vertecies)
        self.program['width'] = self.physical_size[0]
        self.program['hight'] = self.physical_size[1]
        return img

    def save_img(self):
        print("saving img to: %s" %  self.output_file_name)
        misc.imsave(self.output_file_name, self.render_img())

    def on_key_press(self, event):
        if event.key == 'S':
            self.save_img()


def get_img(input_img, strength, size):
    c = Canvas(input_img, strength, size, False)
    return c.render_img()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("please specify an input path or use the help keyword to get help")
    elif sys.argv[1] == 'help' or sys.argv[1] == '--help':
        print('''
WELCOME TO XKCD CONVERTER
This is a small commandline tool used to convert pixel graphigs to
xkcd style.

USAGE:
OPTIMIZE STRENGTH VALUE:
py xkcd.py Relative_File_Path Noise_map_size output_file_name Strength_in_percent
In the Application, use the mouse wheel to pick a sutabple strength value,
than press 'S' to save to the output_file_name
JUST SAVE THE IMAGE:
py xkcd.py Relative_File_Path Noise_map_size output_file_name Strength_in_percent Now
creates the image right away
        ''')
    elif os.path.exists(sys.argv[1]) and len(sys.argv) < 6:
        strength, size, output_file_name = 1, 32, "screen.png"
        if len(sys.argv) >= 3:
            size = int(sys.argv[2])
        if (len(sys.argv)) >= 4:
            output_file_name = sys.argv[3]
        if len(sys.argv) >= 5:
            strength = float(sys.argv[4])
        print("Using input path: %s strength: %s%% size: %s, output_file_name = %s" %
                (sys.argv[1], strength, size, output_file_name))
        c = Canvas(sys.argv[1], strength, size, output_file_name=output_file_name)
        app.run()
    elif len(sys.argv) == 6:
        Canvas(sys.argv[1], float(sys.argv[4]), int(sys.argv[2]), False, sys.argv[3]).save_img()
    else:
        print("Error, pleas provide a valid input file path or use the 'help' flag to get help")

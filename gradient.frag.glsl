#ifdef GL_ES
precision highp float;
#endif

const int MAXCOLORS = 10;

uniform vec4 colors[MAXCOLORS];
uniform float numOfColors;
uniform float angle;
uniform float startMixBoundary;
uniform float endMixBoundary;

varying vec2 texCoord;
varying vec4 vertexColor;

vec2 rotate(vec2 v, float angle)
{
    vec2 origin = vec2(0.5, 0.5);

    vec2 dir = v - origin;
    float dist = length(dir);
    float targetAngle = atan(dir.y, dir.x) - angle;

    return origin + vec2(cos(targetAngle), sin(targetAngle)) * dist;
}

vec4 getColor(float positionOnPalette)
{
    if (positionOnPalette < 1.0)
    {
        return colors[0];
    }
    if (positionOnPalette < 2.0)
    {
        return colors[1];
    }
    if (positionOnPalette < 3.0)
    {
        return colors[2];
    }
    if (positionOnPalette < 4.0)
    {
        return colors[3];
    }
    if (positionOnPalette < 5.0)
    {
        return colors[4];
    }
    if (positionOnPalette < 6.0)
    {
        return colors[5];
    }
    if (positionOnPalette < 7.0)
    {
        return colors[6];
    }
    if (positionOnPalette < 8.0)
    {
        return colors[7];
    }
    if (positionOnPalette < 9.0)
    {
        return colors[8];
    }
    return colors[9];
}

void main()
{
    float paletteSize = clamp(numOfColors - 1.0, 0.0, float(MAXCOLORS - 1));

    float palettePart = rotate(texCoord, angle).x;
    palettePart = clamp(palettePart, 0.0, 1.0);
    float positionOnPalette = palettePart * paletteSize;

    vec4 currentColor = getColor(positionOnPalette);
    vec4 nextColor = getColor(positionOnPalette + 1.0 - step(1.0, palettePart));

    float mixFactor = smoothstep(startMixBoundary, endMixBoundary, fract(positionOnPalette));

    gl_FragColor = mix(currentColor, nextColor, mixFactor) * vertexColor;
}
#pragma once

namespace ControlCenter
{
class CornerGesture
{
  public:
    void begin(int x, int y)
    {
        startX = x;
        startY = y;
        cancelled = false;
    }
    bool move(int x, int y)
    {
        const int dx = x - startX;
        const int dy = y - startY;
        if (dx > 24 || dx < -24 || dy < -12)
            cancelled = true;
        return !cancelled && dy >= 28;
    }
    bool tap(int x, int y) const
    {
        return !cancelled && x - startX < 12 && startX - x < 12 && y - startY < 12 && startY - y < 12;
    }

  private:
    int startX = 0, startY = 0;
    bool cancelled = false;
};
} // namespace ControlCenter
